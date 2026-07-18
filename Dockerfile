FROM espressif/idf:v5.2.2

ARG INCLUDE_CALIBRATION=0

ENV IDF_PATH="/opt/esp/idf/"
WORKDIR "/"

COPY src/main.py /main.py
COPY src/calibration.py /calibration.py
RUN if [ "$INCLUDE_CALIBRATION" = "0" ]; then rm /calibration.py; fi

RUN git clone https://github.com/earlephilhower/mklittlefs.git && \
  cd mklittlefs && \
  git submodule update --init && \
  make dist && \
  ./mklittlefs --version

RUN cd mklittlefs && \
  mkdir -p ~/fs && \
  cp /*.py ~/fs/ && \
  ./mklittlefs -c ~/fs -b 4096 -p 256 -s 0x200000 /fs.bin

CMD ["/bin/bash"]
