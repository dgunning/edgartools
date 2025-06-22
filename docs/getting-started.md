# Edgartools

Welcome to **edgartools**, the easiest way to work with SEC filings in Python



# Getting Started

---

## 1. Install
```bash
pip install edgartools
```
There are frequent releases so it is a good idea to use `pip install -U edgartools` to get new features and bug fixes.
That being said we try to keep the API stable and backwards compatible.

If you prefer **uv** instead of **pip** you can use the following command:

```bash
uv pip install edgartools
```

## 2. Import edgar

The main way to use the library is to import everything with `from edgar import *`. This will give you access to most of the functions and classes you need.

```
from edgar import *
```

If you prefer a minimal import you can use the following:


## 3. Set your identity

Before you can access the SEC Edgar API you need to set the identity that you will use to access Edgar.
This is usually your **name** and **email**, but you can also just use an email.

You can set your identity in Python before you start using the library. 

### Setting your identity in Python
```python
from edgar import *
set_identity("mike.mccalum@indigo.com")
```

### Setting your identity using an environment variable
You can also set your identity using an environment variable. This is useful if you are using the library in a script or notebook.

```bash 
export EDGAR_IDENTITY="mike.mccalum@indigo.com"
```