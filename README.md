# prepare environment

1. you need to build packages on AWS Amazon Linux

    ```mkdir package
    cd package
    pip install -t . pandas
    pip install -t . xlrd
    cp lambda_function.py .
    zip -r9 ../package.zip .```

2. upload package to lambda
