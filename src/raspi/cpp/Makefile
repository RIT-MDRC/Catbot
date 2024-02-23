output/main: main.o motor.o potentiometer.o limitSwitch.o
	g++ -o output/main -g output/main.o output/motor.o output/potentiometer.o output/limitSwitch.o -lpigpio -lrt

main.o:
	g++ -c -g -Wall -o output/main.o main.cpp -lpigpio -lrt

motor.o: io_controller/motor.cpp io_controller/motor.h
	g++ -c -g -Wall -o output/motor.o io_controller/motor.cpp -lpigpio -lrt

potentiometer.o: io_controller/potentiometer.cpp io_controller/potentiometer.h
	g++ -c -g -Wall -o output/potentiometer.o io_controller/potentiometer.cpp -lpigpio -lrt

clean:
	rm -rf output/*.o
	rm -rf output/main