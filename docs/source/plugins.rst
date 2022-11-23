========
Plugins
========

List of various plugins for goblet to other open source projects or for goblet directly.

Pydantic plugin for APISpec
***************************

Support for pydantic models in the `APISpec <https://apispec.readthedocs.io/en/latest/>`__ project. This plugin is used behind the 
scenes already in goblet to support pydantic and generate openapi specs. 

If you use a custom schema type you can create a schema class that inherits from a pydantic BaseClass. 

.. code:: python 

    from pydantic import BaseModel
    # Pydantic Models
    class NestedModel(BaseModel):
        text: str
    class PydanticModel(BaseModel):
        id: int
        nested: NestedModel
    # Request Body Typing
    @app.route("/pydantic", request_body=PydanticModel)
    def traffic() -> PydanticModel:
        return jsonify(PydanticModel().dict)


If you want to return the Pydantic class to use IDE typing linting instead of the jsonified dict above, you can use the 
after_request middleware to handle the response formatting. 

.. code:: python

    @app.after_request()
    def pydantic_response(response):
        if isinstance(response, BaseModel):
            return jsonify(response.dict())
        else:
            return jsonify(response)

    @app.route("/pydantic", request_body=PydanticModel)
    def traffic() -> PydanticModel:
        return PydanticModel()