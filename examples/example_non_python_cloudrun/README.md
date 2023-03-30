# Example Non Python Cloud Run

This example follows [this tutorial](https://bikramat.medium.com/dockerfile-node-example-bbd53a2caf0a) to setup a quick sample node app. 

To deploy simply add a `main.py` with the following code

```python
from goblet import Goblet

app = Goblet(
    function_name="goblet-node", backend="cloudrun"
)
```

and run 

`goblet deploy -p PROJECT -l LOCATION`
