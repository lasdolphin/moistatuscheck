import boto3
import json
import unittest

region = 'eu-central-1'

payload1 = """{
  "dry": 1,
  "update_id": 4,
  "message": {
    "message_id": 261,
    "from": {
      "id": 427355455,
      "is_bot": "True",
      "first_name": "qwe",
      "last_name": "qwe",
      "language_code": "en"
    },
    "chat": {
      "id": 61560729,
      "first_name": "qwe",
      "last_name": "qwe",
      "type": "private"
    },
    "date": 1556618119,
    "text": "OAM-47516/ZM-2018"
  }
}"""

payload2 ="""{
  "dry": 1,
  "update_id": 5,
  "message": {
    "message_id": 261,
    "from": {
      "id": 427355455,
      "is_bot": "True",
      "first_name": "qwe",
      "last_name": "qwe",
      "language_code": "en"
    },
    "chat": {
      "id": 61560729,
      "first_name": "qwe",
      "last_name": "qwe",
      "type": "private"
    },
    "date": 1556618119,
    "text": "OAM-47516-2/ZM-2018"
  }
}"""

payload3 ="""{
  "dry": 1,
  "update_id": 6,
  "message": {
    "message_id": 261,
    "from": {
      "id": 427355455,
      "is_bot": "True",
      "first_name": "qwe",
      "last_name": "qwe",
      "language_code": "en"
    },
    "chat": {
      "id": 61560729,
      "first_name": "qwe",
      "last_name": "qwe",
      "type": "private"
    },
    "date": 1556618119,
    "text": "OAM-12906/ZM-2018"
  }
}"""
def invoke_lambda(payload, region):
    client = boto3.client('lambda', region_name = region)
    response = client.invoke(
        FunctionName="MOIStatusCheck",
        InvocationType='RequestResponse',
        Payload=payload
    )
    return json.loads(response['Payload'].read())

class TestLambda(unittest.TestCase):

    def test_found(self):
        self.assertIn('found in MOI', invoke_lambda(payload1, region))

    def test_wrong_format(self):
        self.assertIn('Format seems to be incorrect', invoke_lambda(payload2, region))

    def test_bot_found(self):
        self.assertIn('was not found in file from', invoke_lambda(payload3, region))

if __name__ == '__main__':
    unittest.main()
