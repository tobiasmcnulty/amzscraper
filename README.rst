Amazon Order Scraper
====================

This is a simple script using the Python ``mechanize`` library to scrape all your Amazon
orders and create handy PDFs for receipt/tax purposes.

To use::

    git clone https://github.com/tobiasmcnulty/amzscraper.git
    mkvirtualenv amzscraper
    pip install -r requirements.txt
    python amz.py -u <email> -p <pass> 2013 2014 2015

If you have memcached running locally (recommended), it will cache URL contents for six
hours to avoid spamming Amazon. If it does need to download a page from Amazon, a random
sleep is inserted to throttle connections to the server.

Orders will be downloaded to the ``orders/`` directory in your current directory by
default

For further options, see::

    python amz.py -h

Requirements
------------

* Python 2.7
* ``virtualenv`` and ``virtualenvwrapper``
* ``wkhtmltopdf`` installed and in your ``PATH``
* ``memcached`` running locally, for caching

Credits
-------

This is loosely based on an `earlier project <http://chase-seibert.github.io/blog/2011/01/15/backup-your-amazon-order-history-with-python.html>`_
by Chase Seibert.
