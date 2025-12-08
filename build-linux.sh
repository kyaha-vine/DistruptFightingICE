#!/bin/bash

# Generate Protocol Buffers files
echo "Generating Protocol Buffers files..."
mkdir -p src_python
protoc -I=protos --java_out=src protos/*.proto
protoc -I=protos --python_out=src_python protos/*.proto

# Find all Java files in the src directory and save them to sources.txt
find src -name "*.java" > sources.txt

# Compile the Java files
# Include all jar files in lib and its subdirectories in the classpath
javac -cp "bin:lib/*:lib/lwjgl/*:lib/lwjgl/natives/linux/amd64/*:lib/grpc/*" -d bin @sources.txt

# Check if compilation was successful
if [ $? -eq 0 ]; then
    echo "Build successful."
else
    echo "Build failed."
    exit 1
fi
