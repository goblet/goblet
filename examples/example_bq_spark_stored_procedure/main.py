import logging
from goblet import Goblet, goblet_entrypoint
# from spark import spark_handler

app = Goblet(function_name="create-bq-spark-stored-procedure")

app.log.setLevel(logging.DEBUG)  # configure goblet logger level
goblet_entrypoint(app)

# Create a bq spark stored procedure with the spark code and additional python files
app.bqsparkstoredprocedure(
    name="count_words_procedure_external",
    dataset_id="tutorial",
    spark_file="spark.py",
    additional_python_files=["additional.py"],
)

# Create a bq spark stored procedure with the spark code from the function
# app.bqsparkstoredprocedure(
#     name="count_words_procedure",
#     dataset_id="tutorial",
#     func=spark_handler,
# )
