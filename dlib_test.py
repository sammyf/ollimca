#!/bin/python
import dlib as cuda
print(cuda.get_num_devices())  # Should return 1 or more if GPU detected