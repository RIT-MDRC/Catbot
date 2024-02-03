#include <pigpio.h>
#include <stdexcept>

class Motor {

    public:
        /**
         * Creates an instance of a motor. There should be one instance of this per real-world motor.
         * pwmPin: The pin number of the PWM pin.
         * directionPin: The pin number of the direction pin.
        */
        Motor(int pwmPin, int directionPin);

        /**
         * Updates the speed and direction of the motor
         * clockwise: If true turns clockwise; otherwise counterclockwise (when viewing from the front of motor).
         * speed: [0-255], where 0 is no motion and 255 is max speed.
        */
        void run(bool clockwise, int speed);

        /**
         * Stops the motor.
        */
        void stop();
    private:
        int pwmPin;
        int directionPin;
};