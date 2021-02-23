Amazon Order Scraper
====================

This is a simple script using the Python selenium library to scrape all your Amazon
orders and create handy PDFs for receipt/tax purposes.

To use::

    mkvirtualenv -p python3.9 amzscraper
    pip install git+https://github.com/tobiasmcnulty/amzscraper.git
    amscraper -u <email> -p <pass> 2021

A random sleep is inserted to throttle connections to the server.

Orders will be downloaded to the ``orders/`` directory in your current directory by
default.

For further options, see::

    amzscraper -h

Requirements
------------

* Python 3.7+
* ``virtualenv`` and ``virtualenvwrapper``
* ``wkhtmltopdf`` installed and in your ``PATH``
* ``chromedriver`` installed and in your ``PATH``

Credits
-------

This is loosely based on an `earlier project <http://chase-seibert.github.io/blog/2011/01/15/backup-your-amazon-order-history-with-python.html>`_
by Chase Seibert.
