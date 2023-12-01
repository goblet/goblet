# BigQuery Spark Stored Procedure Example
This example demonstrates how to use Goblet to create a BigQuery stored procedure that uses Spark. https://cloud.google.com/bigquery/docs/spark-procedures

## Running Example
```bash
# Run the example. This will create a topic and a subscription on the emulator.
goblet deploy --skip-backend
bq query --use_legacy_sql=false --destination_table=myDataset.myTable \
    'CALL `project.myDataset.count_words_procedure_external`();'
```
