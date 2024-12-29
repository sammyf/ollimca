git clone https://github.com/davisking/dlib.git
cd dlib
git submodule init
git submodule update
mkdir build
cd build
cmake .. -DCUDA_NVCC_EXECUTABLE=$(which nvcc) -DDLIB_USE_CUDA=1 -D USE_AVX_INSTRUCTIONS=1
cmake --build .
cd ..
pip install .
