# Architecture

The inventory service is a single script, `inventory.py`, that reads and writes
`inventory.json` directly. Commands are parsed with `sys.argv`.

```
inventory.py  <-->  inventory.json
```

(Last updated before the 0.2 restructure.)
