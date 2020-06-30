import argparse
import datetime
import hashlib
import itertools
import os
import random
import re
import smtplib
import subprocess
import sys
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

import memcache
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException


def rand_sleep(max_seconds=5):
    """
    Wait a little while so we don't spam Amazon.
    """
    seconds = random.randint(2, max_seconds)
    print("Sleeping for %s seconds..." % seconds, end="")
    sys.stdout.flush()
    time.sleep(seconds)
    print("done.")


class AmzMechanize(object):
    """ Use Python mechanize to login and retrieve URLs. Broken as of May 2016. """

    headers = [
        # ('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.13) '
        #                'Gecko/20101206 Ubuntu/10.10 (maverick) Firefox/3.6.13')
        (
            "User-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
        )
    ]

    def __init__(self):
        import mechanize

        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)
        self.br.addheaders = self.headers

    def login(self, email, password):
        self.br.open("https://www.amazon.com")
        resp = self.br.follow_link(text_regex="Hello. Sign in")
        self.br.select_form(nr=0)
        self.br["email"] = email
        self.br["password"] = password
        resp = self.br.submit()
        if resp.code != 200:
            raise Exception("Got invalid response code %s" % resp.code)
        elif resp.geturl().startswith(
            "https://www.amazon.com/ap/signin"
        ):  # not the URL we wanted
            html = resp.get_data()
            soup = BeautifulSoup(html, "lxml")
            err = soup.find_all("div", attrs={"id": "message_error"})
            warn = soup.find_all("div", attrs={"class": "a-alert-content"})
            msg = (
                err
                and err[0].renderContents()
                or (warn and warn[0].renderContents())
                or html
            ).strip()
            raise Exception("Login failed for %s, %s:\n%s" % (email, password, msg))

    def get_url(self, url):
        return self.br.open(url).get_data()

    def clean_up(self):
        pass


class AmzChromeDriver(object):
    """
    Replacement driver to login to Amazon and download URLs using the Selenium
    ChromeDriver.
    """

    def __init__(self):
        from selenium import webdriver

        self.driver = webdriver.Chrome("/usr/local/bin/chromedriver")
        self.driver.implicitly_wait(5)

    def login(self, email, password):
        driver = self.driver
        driver.get("https://www.amazon.com/")
        rand_sleep()
        driver.find_element_by_css_selector(
            "#nav-signin-tooltip > a.nav-action-button"
        ).click()
        rand_sleep()
        driver.find_element_by_id("ap_email").clear()
        driver.find_element_by_id("ap_email").send_keys(email)
        # Sometimes there is a Continue button after entering your email;
        # sometimes there isn't.
        try:
            driver.find_element_by_id("continue").click()
            rand_sleep()
        except NoSuchElementException:
            print("No continue button found; ignoring...")
        driver.find_element_by_id("ap_password").clear()
        driver.find_element_by_id("ap_password").send_keys(password)
        driver.find_element_by_id("signInSubmit").click()

    def get_url(self, url):
        self.driver.get(url)
        # doesn't always work the first time, so get the page twice (agh!)
        time.sleep(1)
        self.driver.get(url)
        return self.driver.page_source

    def clean_up(self):
        self.driver.quit()


class Emailer(object):
    def __init__(self, smtp_host, smtp_port, smtp_user, smtp_password):
        self.smtp_host = smtp_host
        self.smtp_port = int(smtp_port)
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password

    def send_mail(self, send_from, send_to, subject, text, files=None):
        assert isinstance(send_to, list)
        msg = MIMEMultipart()
        msg["From"] = send_from
        msg["To"] = COMMASPACE.join(send_to)
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = subject
        msg.attach(MIMEText(text))

        for f in files or []:
            with open(f, "rb") as fil:
                print("attaching", os.path.basename(f))
                msg.attach(
                    MIMEApplication(
                        fil.read(),
                        "pdf",
                        name=os.path.basename(f),
                        Content_Disposition='attachment; filename="%s"'
                        % os.path.basename(f),
                    )
                )

        smtp = smtplib.SMTP(self.smtp_host, self.smtp_port)
        smtp.starttls()
        smtp.login(self.smtp_user, self.smtp_password)
        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.close()


class AmzScraper(object):

    base_url = "https://www.amazon.com"
    start_url = (
        base_url
        + "/gp/css/history/orders/view.html?orderFilter=year-{yr}&startAtIndex=1000"
    )
    order_url = (
        base_url
        + "/gp/css/summary/print.html/ref=od_aui_print_invoice?ie=UTF8&orderID={oid}"
    )

    order_date_re = re.compile(r"Order Placed:")
    order_id_re = re.compile(r"orderID=([0-9-]+)")

    def __init__(
        self,
        year,
        user,
        password,
        dest_dir,
        cache_timeout,
        from_email,
        to_email,
        brcls=AmzChromeDriver,
        emailer=None,
    ):
        self.year = year
        self.orders_dir = dest_dir
        self.cache_timeout = cache_timeout
        self.from_email = from_email
        self.to_email = to_email
        self.emailer = emailer
        self.mc = memcache.Client(["127.0.0.1:11211"], debug=0)
        self.br = brcls()
        self.br.login(user, password)

    def _fetch_url(self, url, use_cache=True):
        key = hashlib.md5(url.encode("utf-8")).hexdigest()
        val = use_cache and self.mc.get(key.encode("utf-8")) or None
        if not val:
            print("fetching %s from server (with random sleep)" % url)
            val = self.br.get_url(url)
            rand_sleep()
            self.mc.set(key, val, self.cache_timeout)
            from_cache = False
        else:
            print("using cache for %s" % url)
            from_cache = True
        return val, from_cache

    def get_order_nums(self):
        order_nums = set()
        url = self.start_url.format(yr=self.year)
        for page_num in itertools.count(start=2, step=1):
            html, _ = self._fetch_url(url)
            soup = BeautifulSoup(html, "lxml")
            order_links = soup.find_all("a", href=self.order_id_re)
            order_nums |= set(
                [self.order_id_re.search(link["href"]).group(1) for link in order_links]
            )
            page_links = soup.find_all("a", text=str(page_num))
            if not page_links:
                print("found no links for page_num=%s; assuming completion" % page_num)
                break
            url = self.base_url + page_links[0]["href"]
        print("found %s orders in %s" % (len(order_nums), self.year))
        return order_nums

    def run(self):
        order_nums = self.get_order_nums()
        for oid in order_nums:
            orders = os.listdir(self.orders_dir)
            if any(["{oid}.pdf".format(oid=oid) in o for o in orders]):
                print("skipping order %s (already exists)" % oid)
                continue
            url = self.order_url.format(oid=oid)
            html, from_cache = self._fetch_url(url)
            # force a re-fetch if we got a non-final order from the cache:
            if "Final Details for Order #" not in html and from_cache:
                html, _ = self._fetch_url(url, use_cache=False)
            if "Final Details for Order #" not in html:
                print("skipping order %s (not final)" % oid)
                continue
            soup = BeautifulSoup(html, "lxml")
            order_txt = soup.find_all(text=self.order_date_re)[0]
            date = order_txt.parent.next_sibling.strip()
            date = datetime.datetime.strptime(date, "%B %d, %Y").strftime("%Y-%m-%d")
            fn = "amazon_order_{date}_{oid}.".format(date=date, oid=oid) + "{ext}"
            fn = os.path.join(self.orders_dir, fn)
            with open(fn.format(ext="html"), "w") as f:
                f.write(html)
            subprocess.check_call(
                [
                    "wkhtmltopdf",
                    "--no-images",
                    "--disable-javascript",
                    fn.format(ext="html"),
                    fn.format(ext="pdf"),
                ]
            )
            os.remove(fn.format(ext="html"))
            if self.from_email and self.to_email and self.emailer:
                # email the PDF
                subject = os.path.basename(fn.format(ext="pdf"))
                body = ""
                self.emailer.send_mail(
                    self.from_email,
                    [self.to_email],
                    subject,
                    body,
                    [os.path.abspath(fn.format(ext="pdf"))],
                )
            else:
                print("skipping email send for order %s" % oid)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape an Amazon account and create order PDFs."
    )
    parser.add_argument(
        "-u", "--user", required=True, help="Amazon.com username (email)."
    )
    parser.add_argument("-p", "--password", required=True, help="Amazon.com password.")
    parser.add_argument("--smtp-user", required=False, help="SMTP username (optional).")
    parser.add_argument(
        "--smtp-password", required=False, help="SMTP password (optional)"
    )
    parser.add_argument("--smtp-host", required=False, help="SMTP host (optional)")
    parser.add_argument("--smtp-port", required=False, help="SMTP port (optional)")
    parser.add_argument(
        "--from-email", required=False, help="From email (for sending emails)."
    )
    parser.add_argument(
        "--to-email", required=False, help="To email (for sending emails)."
    )
    parser.add_argument(
        "--cache-timeout",
        required=False,
        default=21600,
        help="Timeout for URL caching, in seconds. Defaults to 6 hours.",
    )
    parser.add_argument(
        "--dest-dir",
        required=False,
        default="orders/",
        help='Destination directory for scraped order PDFs. Defaults to "orders/"',
    )
    parser.add_argument(
        "year",
        nargs="*",
        type=int,
        default=datetime.datetime.today().year,
        help="One or more years for which to retrieve orders. Will default to the "
        "current year if no year is specified.",
    )
    return parser.parse_args()


def main():
    args = vars(parse_args())
    smtp_args = {k: args.pop(k) for k in list(args.keys()) if k.startswith("smtp_")}
    if len(smtp_args) == 4:
        emailer = Emailer(**smtp_args)
    elif len(smtp_args) == 0:
        emailer = None
    else:
        raise Exception("Did not get 0 or 4 SMTP arguments.")
    years = args.pop("year")
    for year in years:
        AmzScraper(year=year, emailer=emailer, **args).run()


if __name__ == "__main__":
    main()
