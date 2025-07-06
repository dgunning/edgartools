# Installation

Get started with edgartools in minutes. This guide covers all installation methods and system requirements.

## System Requirements

- **Python**: 3.8 or higher

## Quick Installation

### Using pip (Recommended)

```bash
pip install edgartools
```

For the latest features and bug fixes:

```bash
pip install -U edgartools
```

### Using uv (Fast Alternative)

```bash
uv pip install edgartools
```

## Development Installation

If you want to contribute or use the latest development version:

```bash
# Clone the repository
git clone https://github.com/dgunning/edgartools.git
cd edgartools

# Install in development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Verify Installation

Test your installation by running this simple command:

```python
from edgar import get_filings
print("EdgarTools installed successfully!")
```

Expected output:
```
EdgarTools installed successfully!
```

If you see this message, your installation is successful. 

If you see `ImportError: cannot import name 'get_filings' from 'edgar'` then you have likely installed another package named **edgar** not **edgartools**.
If you encounter this error, uninstall the conflicting package and reinstall edgartools:

```bash
pip uninstall edgar
pip install edgartools
```

## Setting Your Identity

Before using edgartools, you must set your identity to comply with SEC requirements:

### Method 1: In Python Code

```python
from edgar import set_identity

# Use your name and email
set_identity("John Doe john.doe@company.com")

# Or just your email
set_identity("john.doe@company.com")
```

### Method 2: Environment Variable

Set the `EDGAR_IDENTITY` environment variable:

**Linux/macOS:**
```bash
export EDGAR_IDENTITY="John Doe john.doe@company.com"
```

**Windows:**
```cmd
set EDGAR_IDENTITY=John Doe john.doe@company.com
```

**Windows PowerShell:**
```powershell
$env:EDGAR_IDENTITY = "John Doe john.doe@company.com"
```

## Optional Dependencies

For enhanced functionality, install these optional packages:

## Troubleshooting

### Common Issues

#### ImportError: No module named 'edgar'

**Problem**: Package not installed correctly
**Solution**: 
```bash
pip uninstall edgar
pip install --force-reinstall edgartools
```

#### SEC Identity Error

**Problem**: Identity not set
**Solution**: Follow the [Setting Your Identity](#setting-your-identity) section above

#### Permission Errors on Windows

**Problem**: Insufficient permissions
**Solution**: Run as administrator or use `--user` flag:
```bash
pip install --user edgartools
```

#### SSL Certificate Errors

**Problem**: Corporate firewall or proxy
**Solution**: Configure pip for your proxy:
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org edgartools
```

#### Memory Issues with Large Datasets

**Problem**: Out of memory errors
**Solution**: 
- Increase system memory
- Use data chunking techniques
- Process data in smaller batches

### Getting Help

If you encounter issues:

1. **Search existing issues**: [GitHub Issues](https://github.com/dgunning/edgartools/issues)
2. **Create a new issue**: Include Python version, OS, and error messages
3. **Join the community**: Discussions and support channels

## Virtual Environment Setup

For isolated development, use virtual environments:

### Using venv (Python 3.8+)

```bash
# Create virtual environment
python -m venv edgar-env

# Activate (Linux/macOS)
source edgar-env/bin/activate

# Activate (Windows)
edgar-env\Scripts\activate

# Install edgartools
pip install edgartools

# Deactivate when done
deactivate
```


## Performance Optimization

For optimal performance:

1. **Use Local Storage** to download and work with SEC filings locally
3. **Set reasonable limits** when querying large datasets
4. **Use filtering** to reduce data transfer

## Next Steps

After installation:

1. **Read the [Quick Start Guide](quickstart.md)** for your first analysis
2. **Check the [API Reference](api/company.md)** for detailed documentation

## Security Considerations

- **Never commit your identity** to version control
- **Use environment variables** for production deployments
- **Follow SEC rate limits** to avoid being blocked
- **Keep your installation updated** for security patches

## License

EdgarTools is released under the MIT License. See [LICENSE](https://github.com/dgunning/edgartools/blob/main/LICENSE) for details.