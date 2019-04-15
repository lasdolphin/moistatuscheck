FROM amazonlinux:latest

WORKDIR /home/moicheck
RUN yum install -y awscli python3 zip
RUN pip3 install -t . pandas xlrd
RUN zip -r9 ../moicheck.zip .

CMD ["/bin/bash"]
