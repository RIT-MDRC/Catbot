#include <pigpio.h>
#include <stdexcept>

#define PWM_FREQUENCY 100   // (in hertz)
#define PWM_RANGE 255

// Latch pins
#define PIN_MOTOR_DIR 1     // data to write for direction
#define PIN_LATCH_EN 15     // latch enable (active low)
int LATCH_ADDRESS_PINS = { 12, 6, 5 }   // 0th index is least significant bit

class Motor {

    public:
        /**
         * Creates an instance of a motor. There should be one instance of this per real-world motor.
         * pwmPin: The pin number of the PWM pin.
         * directionPin: The pin number of the direction pin.
        */
        Motor(int pwmPin, int latchAddress);

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
        int latchAddress;
};