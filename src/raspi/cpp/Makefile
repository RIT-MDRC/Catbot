include cpp.env

ifeq ($(ENV), "dev")
output/main: main.o motor.o
	g++ -o output/main -g output/main.o output/motor.o 

main.o:
	g++ -c -g -Wall -D COMPUTER -o output/main.o main.cpp

motor.o: io_controller/motor.cpp io_controller/motor.h
	g++ -c -g -Wall -D COMPUTER -o output/motor.o io_controller/motor.cpp

else
output/main: main.o motor.o
	g++ -o output/main -g output/main.o output/motor.o -lpigpio -lrt

main.o:
	g++ -c -g -Wall -D ROBOT -o output/main.o main.cpp -lpigpio -lrt

motor.o: io_controller/motor.cpp io_controller/motor.h
	g++ -c -g -Wall -D ROBOT -o output/motor.o io_controller/motor.cpp -lpigpio -lrt

endif

clean:
	rm -rf output/*.o
	rm -rf output/main
