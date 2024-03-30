motor.so:
	g++ -I/boost_1_72/ -I/usr/include/python3.11/ io_controller/motor.cpp -fPIC -lboost_python311 -Wl,-soname,motor -shared -o io_controller/motor.so -lpigpio -lrt

clean:
	rm -r */.so