def spark_handler():
    from pyspark.sql import SparkSession
    import pyspark.sql.functions as F

    spark = SparkSession.builder.appName("spark-bigquery-demo").getOrCreate()

    # Load data from BigQuery.
    texts = spark.read.format("bigquery").option("table", "tutorial.poc").load()
    texts.createOrReplaceTempView("words")

    # Perform word count.
    text_count = texts.select("id", "text", F.length("text").alias("sum_text_count"))
    text_count.show()
    text_count.printSchema()

    # Saving the data to BigQuery
    text_count.write.mode("append").format("bigquery").option(
        "writeMethod", "direct"
    ).save("tutorial.wordcount_output")


if __name__ == "__main__":
    spark_handler()
