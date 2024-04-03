include	../.env # if this is saying that there is a seperator check the env file that any documentation is commented out

ifeq ($(ENV), "dev")
LIBRARIES= 
DEFINITION=COMPUTER
else
LIBRARIES=-lpigpio -lrt
DEFINITION=ROBOT
endif


output/main: main.o motor.o
	g++ -o output/main -g output/main.o output/motor.o 

main.o:
	g++ -c -g -Wall -D $(DEFINITION) -o output/main.o main.cpp $(LIBRARIES)

motor.o: io_controller/motor.cpp io_controller/motor.h
	g++ -c -g -Wall -D COMPUTER -o output/motor.o io_controller/motor.cpp

clean:
	rm -rf output/*.o
	rm -rf output/main
