# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Base image with CUDA 12.5.1 and Ubuntu 22.04
FROM nvidia/cuda:12.5.1-devel-ubuntu22.04

RUN apt-get update && apt-get upgrade -y

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get install -y \
    cmake \
    cmake-data \
    build-essential \
    python3.10 \
    python3-dev \
    python3-pip \
    libopencv-dev \
    pkg-config \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libdc1394-dev \
    curl

RUN pip3 install numpy flask

WORKDIR /opencv
RUN curl -L https://github.com/opencv/opencv/archive/refs/tags/4.10.0.tar.gz > opencv.tar.gz
RUN tar -xvzf opencv.tar.gz
RUN curl -L https://github.com/opencv/opencv_contrib/archive/refs/tags/4.10.0.tar.gz > opencv_contrib.tar.gz
RUN tar -xvzf opencv_contrib.tar.gz

RUN mv opencv-4.10.0 opencv
RUN mv opencv_contrib-4.10.0 opencv_contrib
RUN rm *.tar.gz

WORKDIR /opencv/opencv
RUN mkdir build
WORKDIR /opencv/opencv/build

RUN cmake -D CMAKE_BUILD_TYPE=Release \
        -D CMAKE_INSTALL_PREFIX=/usr/local \
        -D OPENCV_EXTRA_MODULES_PATH=/opencv/opencv_contrib/modules/ \
        -D PYTHON3_EXECUTABLE=/usr/bin/python3 \
        -D PYTHON3_INCLUDE_DIR=/usr/include/python3.10/ \
        -D PYTHON3_INCLUDE_DIR2=/usr/include/x86_64-linux-gnu/python3.10/ \
        -D PYTHON3_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython3.10.so \
        -D PYTHON3_NUMPY_INCLUDE_DIRS=/usr/local/lib/python3.10/dist-packages/numpy/_core/include/ \
        -D OPENCV_GENERATE_PKGCONFIG=ON \
        -D OPENCV_PC_FILE_NAME=opencv.pc \
        -D WITH_CUDA=ON \
        -D WITH_CUDNN=ON \
        -D OPENCV_DNN_CUDA=OFF \
        -D CUDA_ARCH_BIN=8.6 \
        -D ENABLE_FAST_MATH=ON \
        -D CUDA_FAST_MATH=ON \
        -D WITH_CUFFT=ON \
        -D WITH_CUBLAS=ON \
        -D WITH_V4L=ON \
        -D WITH_OPENCL=ON \
        -D WITH_OPENGL=ON \
        -D WITH_GSTREAMER=ON \
         D BUILD_TESTS=OFF \
        -D BUILD_PERF_TESTS=OFF \
        -D BUILD_EXAMPLES=OFF \
        -D BUILD_opencv_apps=OFF \
        -D WITH_TBB=ON ..

RUN make -j $(nproc)
RUN make install
RUN rm -rf /opencv/opencv/build

RUN mkdir /app
WORKDIR /app

COPY . .
ENV FLASK_APP app.py

RUN pip install -r requirements.txt
RUN mkdir -p videos

ENTRYPOINT ["./entrypoint.sh"]
