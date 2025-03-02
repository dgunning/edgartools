# Insider Filings

Insider filings are reports filed by company insiders (such as officers, directors, and employees) when they buy or sell shares in their own companies. 

There are several types of insider filings that investors should be aware of:

1. **Form 3**: Filed by insiders to report their initial ownership of company stock - typically filed when an insider joins a company or becomes an officer or director.
2. **Form 4**: Filed to report any changes in ownership of company stock - typically filed when an insider buys or sells company stock.
3. **Form 5**: Includes any transactions that were not reported on Form 4 - typically filed at the end of the fiscal year.

## Getting Insider Filings

You can access insider filings using the `get_filings` method of the `Company` class.

```python
c = Company("VRTX")
filings = c.get_filings(form=[3,4,5])
```

You can use either the string or numeric value for the form e.g. "3" or 3.

```python
filings = c.get_filings(form=4)
```

If you are more interested in insider filings non-specific to a particular company, you can use the `get_insider_filings` method of the `Filing` class.

```python   
filings = get_filings(form=[3,4,5])
```

## The Ownership data object
The `Ownership` object is a data object that represents the basic information contained in an insider filing. It is created by parsing the 
XML attachment with the data about the insider transactions in the filing. 

The `Ownership` is subclassed into `Form3`, `Form4`, and `Form5` objects that contain additional information specific to the type of filing.
So if you have a **Form 3** filing you can convert the `Ownership` object to a `Form3` object to get the additional information.

```python
form3 = filing.obj()
```

### Converting Ownership to a dataframe

You can convert the `Ownership` object to a pandas dataframe using the `to_dataframe()` method.

```python
df = form4.to_dataframe()
```
![Form3 Filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/form4-dataframe.png)

By default this will show each of the trades made in that filing. If you want to see the aggregated summary of the trades you can set `detailed=False`

```python
df = form4.to_dataframe(detailed=False)
```

![Form3 Filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/form4-dataframe-summary.png)

By default the dataframe will include metadata about the filing. If you want to exclude the metadata you can set `include_metadata=False`

```python
df = form4.to_dataframe(include_metadata=False)
```
![Form3 Filing No metadata ](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/form4-dataframe-nometadata.png)

The specifics of the data in the dataframe will depend on the type of filing and the information contained in the filing.

## Form 3 - Initial Beneficial Ownership

The `Form3` data object is created from a form 3 filing as follows

```python
form3 = filing.obj()
```

![Form3 Filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/form3.png)


## Form 4 - Changes in Beneficial Ownership

In November 2020 Bruce Sachs, an independent director of Vertex Pharmaceuticals, filed a Form 4 to report the purchase of **15,000** shares of Vertex Pharmaceuticals (VRTX) at an average price of **$217.36** per share.

![Vertex Form4 Filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/vertex-form4-filing.png)

The filing object shows basic information but none of the details of the transaction.
To get the details of the transaction you can use the `obj()` method to convert the filing to a `Form4` object.

```python
form4 = filing.obj()
```
![Vertex Form4 Filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/vertex-form4.png)

The form 4 shows the individual transactions that make up the total transaction. In this case, the total transaction was the purchase of 15,000 shares of Vertex Pharmaceuticals.

Additional information about the transaction can be found in the `TransactionSummary` object.

```python
ownership_summary = form4.get_ownership_summary()
```

![Vertex Ownership Summary](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/ownership_summary.png)


## Form 5 - Annual Changes in Beneficial Ownership

Form 5 filings are essentially the same as Form 4 filings but are filed at the end of the fiscal year to report any transactions that were not reported on Form 4.
So the data in a Form 5 filing will be similar to that in a Form 4 filing.

## Ownership Summary

The `Ownership` object has a `get_ownership_summary()` method that returns either an `InitialOwnershipSummary` for Form 3 filings or a `TransactionSummary` object for Forms 4 and 5. These object contain more specific details about the ownership filing.

```python
ownership_summary = form4.get_ownership_summary()
```

#### Initial Ownership Summary

The `InitialOwnershipSummary` object contains the following fields:

- `total_shares` - the total number of shares owned by the insider
- `has_derivatives` - a boolean indicating whether the insider owns any derivatives
- `no_securities` - a boolean indicating whether the insider owns any securities
- `holdings`: List[SecurityHolding] - a list of SecurityHolding objects representing the insider's holdings

The `SecurityHolding` object is defined as follows:

```python
@dataclass
class SecurityHolding:
    """Represents a security holding (for Form 3)"""
    security_type: str  # "non-derivative" or "derivative"
    security_title: str
    shares: int
    direct_ownership: bool
    ownership_nature: str = ""
    underlying_security: str = ""
    underlying_shares: int = 0
    exercise_price: Optional[float] = None
    exercise_date: str = ""
    expiration_date: str = ""
```

`SecurityHolding` also has these properties

- `ownership_description` - a human-readable description of the type of ownership "Direct/Indirect"
- `is_derivative` - a boolean indicating whether the holding is a derivative



### Transaction Summary

The `TransactionSummary` object is defined as follows:

```python
@dataclass
class TransactionActivity:
    """Represents a specific transaction activity type"""
    transaction_type: str
    code: str
    shares: Any = 0  # Handle footnote references
    value: Any = 0
    price_per_share: Any = None  # Add explicit price per share field
    description: str = ""
```

It also has these properties as a convenience in case any of the expected numeric values are not in fact numeric.

- `shares_numeric` - the number of shares involved in the transaction
- `value_numeric` - the value of the transaction
- `price_numeric` - the price per share of the transaction