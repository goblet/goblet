## Build Goblet Json Schema File for IDE Auto-Complete ##


`build.py` reads source file `utils/schema/base.json` and writes `goblet.schema.json` at the root of the project's directory. 

To rebuild `goblet.schema.json` run:
```bash
$ cd utils/schema
$ python3 build.py
```

### Why does `base.json` need to be processed by `build.py` to output `goblet.schema.json`? ###

`base.json` references Google APIs schema definitions. Unfortunately, the references inside those schema files are not properly referenced within the file structure and when the IDE tries to build autocompletion, it can only go one level down the definition tree. `build.py` downloads the google schema files, fixes the references and saves the files under `utils/schema/references`. Then it writes `goblet.schema.json` using references to those new files.


### How do I use this in my IDE? ### 

`goblet.schema.json` is included in the [SchemaStore Catalog](https://github.com/SchemaStore/schemastore/blob/master/src/api/json/catalog.json).

If your IDE already uses the Schema Store for auto-completion, chances are it is already working in your `.goblet/config.json` file.

To use with *Visual Studio Code* you just need to install the [JSON Schema Store Catalog](https://marketplace.visualstudio.com/items?itemName=remcohaszing.schemastore)

To use with *PyCharm*, click on the **No JSON schema** tab located at the bottom right of the window and search for **Goblet**

If want to use a local version of `goblet.schema.json` with new definitions or references, you can manually add a Json Schema mapping to your IDE.

Here is how to do it in [PyCharm](https://www.jetbrains.com/help/pycharm/json.html#ws_json_schema_add_custom) and [Visual Studio Code](https://code.visualstudio.com/docs/languages/json#_mapping-in-the-user-settings)

