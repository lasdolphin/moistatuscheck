#!/bin/bash
zip -g $1 lambda_function.py
aws lambda --region $region update-function-code --function-name $function_name --zip-file fileb://$1
