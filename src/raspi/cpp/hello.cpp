#include <boost/python.hpp>
#include <iostream>

void greet() { std::cout << "Hello world :)" << std::endl; }

BOOST_PYTHON_MODULE(hello) {
    using namespace boost::python;
    def("greet", greet);
}