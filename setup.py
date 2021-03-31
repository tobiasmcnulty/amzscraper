from setuptools import setup

setup(
    name="amzscraper",
    version="1.0.0",
    description="A helpful utility to scrape and email Amazon receipts.",
    url="https://github.com/tobiasmcnulty/amzscraper",
    author="Tobias McNulty",
    author_email="tobias@caktusgroup.com",
    license="MIT",
    py_modules=["amzscraper"],
    install_requires=[
        "beautifulsoup4==4.9.3",
        "selenium==3.141.0",
        "lxml==4.6.3",
    ],
    entry_points={
        "console_scripts": [
            "amzscraper=amzscraper:main",
        ]
    },
)
