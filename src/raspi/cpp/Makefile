output/main: main.o potentiometer.o
	g++ -o output/main -g output/main.o output/potentiometer.o -lpigpio -lrt

main.o:
	g++ -c -g -Wall -o output/main.o main.cpp -lpigpio -lrt

potentiometer.o: io_controller/potentiometer.cpp io_controller/potentiometer.h
	g++ -c -g -Wall -o output/potentiometer.o io_controller/potentiometer.cpp -lpigpio -lrt

clean:
	rm -rf output/*.o
	rm -rf output/main