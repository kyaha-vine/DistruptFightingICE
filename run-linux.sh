#!/bin/bash

# Run the game
# Include all jar files in lib and its subdirectories in the classpath
# Also include the bin directory where the compiled classes are
java -cp "bin:lib/*:lib/lwjgl/*:lib/lwjgl/natives/linux/amd64/*:lib/grpc/*" Main "$@"
