FROM amazonlinux:latest

WORKDIR /home/moicheck
RUN yum install -y awscli python3 zip && \
    pip3 install -t . pandas xlrd boto3 && \
    zip -r9 ../moicheck.zip .

CMD ["/bin/bash"]
