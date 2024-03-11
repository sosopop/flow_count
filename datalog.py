from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import ASYNCHRONOUS

class DataLog:
    def __init__(self, config):
        self.config = config
        self.db_client = InfluxDBClient(url=config['url'], token=config['token'], org=config['org'])
        self.db_write_api = self.db_client.write_api(write_options=ASYNCHRONOUS)

    def push_data(self, data):
        self.db_write_api.write(bucket=self.config['bucket'], record=data)

    def close(self):
        self.db_client.close()