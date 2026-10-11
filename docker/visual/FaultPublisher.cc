#include <ignition/transport/Node.hh>
#include <ignition/msgs/stringmsg.pb.h>
#include <iostream>
#include <string>
int main(){
  ignition::transport::Node node;
  auto pub=node.Advertise<ignition::msgs::StringMsg>("/navis/propulsion_faults");
  std::string line;
  while(std::getline(std::cin,line)){ignition::msgs::StringMsg msg;msg.set_data(line);pub.Publish(msg);}
}
