FROM nvidia/cuda:11.4.2-cudnn8-devel-ubuntu20.04

ARG OPENCV_VERSION=4.5.4

ENV APP_NAME=mediaserver
ENV WORK_DIR=/usr/src/${APP_NAME}
ENV BUILD_DIR=${WORK_DIR}/build

WORKDIR ${WORK_DIR}

COPY . .

RUN apt-get update && apt-get upgrade -y

RUN DEBIAN_FRONTEND=noninteractive 	\
    apt-get install -y 				\
    build-essential 				\
    vim 							\
    wget 							\
    cmake 							\
    unzip 							\
    pkg-config 						\
    libjpeg-dev 					\
    libpng-dev 						\
    libtiff-dev 					\
    libavcodec-dev 					\
    libavformat-dev 				\
    libswscale-dev 					\
    libv4l-dev 						\
    libxvidcore-dev 				\
    libx264-dev 					\
    libgtk-3-dev 					\
    libatlas-base-dev 				\
    gfortran 						\
    python3-dev  				 && \
    rm -rf /var/lib/apt/lists/*

RUN cd ${BUILD_DIR}                                                     					&& \
    wget https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.zip 					&& \
    unzip ${OPENCV_VERSION}.zip 															&& \
    rm ${OPENCV_VERSION}.zip 																&& \
    wget https://github.com/opencv/opencv_contrib/archive/$OPENCV_VERSION.zip 				&& \
    unzip ${OPENCV_VERSION}.zip 															&& \
    rm ${OPENCV_VERSION}.zip 																&& \
    wget https://bootstrap.pypa.io/get-pip.py 				                                && \
    python3 get-pip.py           															&& \
    pip install numpy           															&& \
    mkdir ${BUILD_DIR}/opencv-${OPENCV_VERSION}/build 										&& \
    cd ${BUILD_DIR}/opencv-${OPENCV_VERSION}/build											&& \
    # Cmake configure
    cmake -D CMAKE_BUILD_TYPE=RELEASE 														   \
    -D CMAKE_INSTALL_PREFIX=/usr/local 														   \
    -D INSTALL_PYTHON_EXAMPLES=OFF 															   \
    -D INSTALL_C_EXAMPLES=OFF 																   \
    -D OPENCV_ENABLE_NONFREE=ON 															   \
    -D WITH_CUDA=ON 																		   \
    -D WITH_CUDNN=ON 																		   \
    -D OPENCV_DNN_CUDA=ON 																	   \
    -D ENABLE_FAST_MATH=1 																	   \
    -D CUDA_FAST_MATH=1 																	   \
    -D CUDA_ARCH_BIN=7.0 																	   \
    -D WITH_CUBLAS=1 																		   \
    -D OPENCV_EXTRA_MODULES_PATH=${BUILD_DIR}/opencv_contrib-${OPENCV_VERSION}/modules 		   \
    -D HAVE_opencv_python3=ON 																   \
    # -D BUILD_EXAMPLES=ON 																	   \
    ..																				        && \
    # Make
    make -j"$(nproc)" 																        && \
    # Install to /usr/local/lib
    make install																	        && \
    ldconfig 																		        && \
    # Remove OpenCV sources and build folder
    rm -rf /opt/opencv-${OPENCV_VERSION} && rm -rf /opt/opencv_contrib-${OPENCV_VERSION}