# prepare environment

1. you need to build packages on AWS Amazon Linux with python 3+

    ```mkdir package
    cd package
    pip install -t . pandas
    pip install -t . xlrd
    cp ../lambda_function.py .
    zip -r9 ../package.zip .```


# deployment

1. export variables ```region``` and ```function_name```
2. use deploy.sh script with package archive name as an argument
```./deploy.sh package.zip```
