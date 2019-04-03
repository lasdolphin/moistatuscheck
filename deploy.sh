#!/bin/bash
zip -g moicheck.zip lambda_function.py
aws lambda --region eu-central-1 update-function-code --function-name MOIStatusCheck --zip-file fileb://moicheck.zip
