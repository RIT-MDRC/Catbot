potentiometer.so:
	g++ -I/boost_1_72/ -I/usr/include/python3.9/ io_controller/potentiometer.cpp -fPIC -lboost_python39 -Wl,-soname,potentiometer -shared -o io_controller/potentiometer.so -lpigpio -lrt

clean:
	rm -r */.so