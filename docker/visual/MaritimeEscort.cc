// Original NAVIS reduced-order surface-craft physics demonstration.
#include "vrx/Wavefield.hh"
#include <algorithm>
#include <atomic>
#include <ignition/msgs/stringmsg.pb.h>
#include <cmath>
#include <ignition/gazebo/System.hh>
#include <ignition/gazebo/Model.hh>
#include <ignition/gazebo/Link.hh>
#include <ignition/gazebo/Util.hh>
#include <ignition/gazebo/components/Model.hh>
#include <ignition/gazebo/components/Name.hh>
#include <ignition/plugin/Register.hh>
#include <ignition/transport/Node.hh>
#include <ignition/msgs/double_v.pb.h>
namespace navis {
using namespace ignition;
class MaritimeEscort : public gazebo::System, public gazebo::ISystemConfigure,
                       public gazebo::ISystemPreUpdate {
  gazebo::Link link;
  gazebo::Entity leader=gazebo::kNullEntity,goalEntity=gazebo::kNullEntity;
  std::string goalName;
  double avoidingUntil=-1,avoidSide=1,avoidLateralSide=1;
  int recoveryStage=0;
  transport::Node node;
  transport::Node::Publisher diagnostics;
  double left=0,right=0,lastReport=-1;
  std::atomic<bool> propulsionFault{false};
  double phase=0,speed=1.5,omega=.007,rx=115,ry=75;
  static double clip(double x,double limit){return std::clamp(x,-limit,limit);}
  vrx::Wavefield wavefield;
 public:
  void Configure(const gazebo::Entity &entity,const std::shared_ptr<const sdf::Element> &sdf,
                 gazebo::EntityComponentManager &ecm,gazebo::EventManager &) override {
    link=gazebo::Link(gazebo::Model(entity).LinkByName(ecm,"base_link"));
    link.EnableVelocityChecks(ecm);
    const std::string modelName=gazebo::Model(entity).Name(ecm);
    node.Subscribe<msgs::StringMsg>("/navis/propulsion_faults",[this,modelName](const msgs::StringMsg &msg){
      propulsionFault.store((","+msg.data()+",").find(","+modelName+",")!=std::string::npos);
    });
    wavefield.Load(sdf);
    goalName=sdf->Get<std::string>("target_model");
    phase=sdf->Get<double>("phase");
    speed=sdf->Get<double>("leader_speed");omega=sdf->Get<double>("angular_speed");
    rx=sdf->Get<double>("radius_x");ry=sdf->Get<double>("radius_y");
    diagnostics=node.Advertise<msgs::Double_V>(sdf->Get<std::string>("diagnostics_topic"));
  }
  void PreUpdate(const gazebo::UpdateInfo &info,gazebo::EntityComponentManager &ecm) override {
    if(info.paused || info.dt.count()<=0)return;
    if(leader==gazebo::kNullEntity)
      leader=ecm.EntityByComponents(gazebo::components::Model(),gazebo::components::Name("SHIP-01"));
    if(leader==gazebo::kNullEntity)return;
    auto velocity=link.WorldLinearVelocity(ecm),angular=link.WorldAngularVelocity(ecm);
    if(!velocity || !angular)return;
    const auto pose=gazebo::worldPose(link.Entity(),ecm);
    const auto lead=gazebo::worldPose(leader,ecm);
    const double t=lead.Pos().X()/speed,dt=std::chrono::duration<double>(info.dt).count();
    if(goalEntity==gazebo::kNullEntity)goalEntity=ecm.EntityByComponents(gazebo::components::Model(),gazebo::components::Name(goalName));
    if(goalEntity==gazebo::kNullEntity)return;
    const auto target=gazebo::worldPose(goalEntity,ecm).Pos();
    const auto error=target-pose.Pos();
    math::Vector3d desired(speed+.3*error.X(),.3*error.Y(),0);
    // Repel from the flagship footprint while moving to a new formation.
    const double relativeX=pose.Pos().X()-lead.Pos().X();
    if(std::abs(relativeX)<92 && std::abs(pose.Pos().Y())<32){
      desired.Y((pose.Pos().Y()<0?-1:1)*std::max(1.2,.3*(32-std::abs(pose.Pos().Y()))));
    }
    const double distance=1000,cpa=1000;const bool avoidance=false;
    // Local separation between escorts augments the mission velocity.
    for(int i=1;i<=10;i++){
      const std::string name="USV-"+(i<10?std::string("0"):std::string())+std::to_string(i);
      auto other=ecm.EntityByComponents(gazebo::components::Model(),gazebo::components::Name(name));
      if(other==gazebo::kNullEntity)continue;
      auto delta=pose.Pos()-gazebo::worldPose(other,ecm).Pos();delta.Z(0);
      double separation=delta.Length();
      if(separation>.1 && separation<18)desired+=delta.Normalized()*((18-separation)*.2);
    }
    if(desired.Length()>5.5)desired=desired.Normalized()*5.5;
    const double yaw=pose.Rot().Yaw();
    const double heading=std::atan2(desired.Y(),desired.X());
    const double yawError=std::atan2(std::sin(heading-yaw),std::cos(heading-yaw));
    const auto bodyV=pose.Rot().RotateVectorReverse(*velocity);
    const double wantedSpeed=desired.Length()*std::max(0.0,std::cos(yawError));
    const double surge=250*(wantedSpeed-bodyV.X())+80*wantedSpeed+25*wantedSpeed*wantedSpeed;
    const double moment=clip(500*yawError-300*angular->Z(),500);
    const double response=1-std::exp(-dt/.5);
    left+=(clip(surge/2-moment/1.4,750)-left)*response;
    right+=(clip(surge/2+moment/1.4,750)-right)*response;
    if(propulsionFault.load()){left=0;right=0;}
    // Four waterplane samples: displaced-volume stiffness and positive-only
    // buoyancy, with vertical damping at each point. Equilibrium draft is .95m.
    for(double x:{-1.8,1.8})for(double y:{-.8,.8}){
      math::Vector3d offset(x,y,-.95);
      const auto arm=pose.Rot().RotateVector(offset);
      const auto point=pose.Pos()+arm;
      const double vz=velocity->Z()+angular->Cross(arm).Z();
      const double force=std::clamp(250*9.81/4+1800*((-.25+wavefield.ComputeDepthDirectly(math::Vector3d(point.X()-lead.Pos().X(),point.Y(),0),std::chrono::duration<double>(info.simTime).count(),0))-point.Z())-300*vz,0.0,1800.0);
      link.AddWorldForce(ecm,math::Vector3d(0,0,force),offset);
    }
    auto forward=pose.Rot().RotateVector(math::Vector3d(1,0,0));
    link.AddWorldForce(ecm,forward*left,math::Vector3d(-1.8,.7,0));
    link.AddWorldForce(ecm,forward*right,math::Vector3d(-1.8,-.7,0));
    math::Vector3d drag(-80*bodyV.X()-25*bodyV.X()*std::abs(bodyV.X()),
                       -200*bodyV.Y()-100*bodyV.Y()*std::abs(bodyV.Y()),0);
    link.AddWorldWrench(ecm,pose.Rot().RotateVector(drag),
                       math::Vector3d(-80*angular->X(),-180*angular->Y(),-100*angular->Z()));
    if(t-lastReport>.5){
      msgs::Double_V msg;
      for(double v:{std::hypot(error.X(),error.Y()),left,right,pose.Pos().Z(),pose.Rot().Roll(),pose.Rot().Pitch(),bodyV.X(),distance,cpa,avoidance?1.0:0.0})msg.add_data(v);
      diagnostics.Publish(msg);lastReport=t;
    }
  }
};
}
IGNITION_ADD_PLUGIN(navis::MaritimeEscort,ignition::gazebo::System,
                   navis::MaritimeEscort::ISystemConfigure,navis::MaritimeEscort::ISystemPreUpdate)
