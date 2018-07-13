#!/usr/bin/env python
import sys
import rospy
import moveit_commander
import geometry_msgs.msg
from moveit_msgs.msg import RobotTrajectory
from ros_reality_bridge.msg import MoveitTarget
from std_msgs.msg import String
import tf


class PlanHandler(object):
    def __init__(self):
        moveit_commander.roscpp_initialize(sys.argv)
        rospy.init_node('move_group_python_interface', anonymous=True)
        self.robot = moveit_commander.RobotCommander()
        self.group_right = moveit_commander.MoveGroupCommander('right_arm')
        self.group_left = moveit_commander.MoveGroupCommander('left_arm')
        print 'pose reference frame before:', self.group_right.get_pose_reference_frame()
        self.group_right.set_pose_reference_frame('/base_link')
        self.group_left.set_pose_reference_frame('/base_link')
        print 'pose reference frame after:', self.group_right.get_pose_reference_frame()
        print 'planning frame:', self.group_left.get_planning_frame()
        self.print_initializer_msgs()
        self.left_arm_plan_publisher = rospy.Publisher('/movo_moveit/left_arm_plan', RobotTrajectory, queue_size=1)
        self.right_arm_plan_publisher = rospy.Publisher('/movo_moveit/right_arm_plan', RobotTrajectory, queue_size=1)
        rospy.Subscriber('/ros_reality/goal_pose', MoveitTarget, self.goal_pose_callback, queue_size=1)
        rospy.Subscriber('/ros_reality/move_to_goal', String, self.execute_goal_callback, queue_size=1)
        # self.listener = tf.TransformListener(True, rospy.Duration(10.0))
        # self.listener.waitForTransform('/base_link', '/odom', rospy.Time(), rospy.Duration(5.0))
        # self.offset_p, self.offset_q = self.listener.lookupTransform('/base_link', '/odom', rospy.Time(0))
        # print 'offset_p:', self.offset_p
        # print 'offset_q:', self.offset_q
        self.plan_to_execute = None
        self.planning = False
        self.arm_to_move = None

    def print_initializer_msgs(self):
        print "================ Robot Groups ==============="
        print self.robot.get_group_names()
        print "================ Robot State ================"
        print self.robot.get_current_state()
        print "============================================="

    def goal_pose_callback(self, data):
        self.planning = True
        moveit_target = data
        self.arm_to_move = moveit_target.arm_to_move.data
        print 'arm_to_move:', self.arm_to_move
        if self.arm_to_move is None:
            return
        print 'planning!'
        if self.arm_to_move == 'right':
            goal_pose = moveit_target.right_arm
            assert isinstance(goal_pose, geometry_msgs.msg.PoseStamped)
            # print 'right arm goal:', goal_pose
            plan = self.generate_plan_right_arm(goal_pose)
            # print 'right arm plan:', plan
            self.plan_to_execute = plan
        elif self.arm_to_move == 'left':
            goal_pose = moveit_target.left_arm
            assert isinstance(goal_pose, geometry_msgs.msg.PoseStamped)
            plan = self.generate_plan_left_arm(goal_pose)
            # print 'left arm plan:', plan
            self.plan_to_execute = plan
        self.planning = False
        print 'done planning!'

    def execute_goal_callback(self, data):
        while self.planning:  # is this necessary?
            continue
        if self.arm_to_move is None:
            return
        if self.plan_to_execute is None:
            print 'execute_goal_callback: no plan to execute!'
            return
        if self.arm_to_move == 'right':
            self.execute_plan_right_arm(self.plan_to_execute)
        else:
            self.execute_plan_left_arm(self.plan_to_execute)

    def get_pose_right_arm(self):
        """
        Get the pose of the right end-effector.
        :return: geometry_msgs.msg.Pose
        """
        return self.group_right.get_current_pose()

    def get_pose_left_arm(self):
        """
        Get the pose of the left end-effector.
        :return: geometry_msgs.msg.Pose
        """
        return self.group_left.get_current_pose()

    def generate_plan_right_arm(self, goal_pose):
        """
        Moves the left end effector to the specified pose.
        :param goal_pose: geometry_msgs.msg.PoseStamped
        :return: RobotTrajectory (None if failed)
        """
        plan = generate_plan(self.group_right, goal_pose)
        if plan is None:
            print 'plan failed :('
            return None
        self.right_arm_plan_publisher.publish(plan)
        return plan

    def generate_plan_left_arm(self, goal_pose):
        """
        Moves the left end effector to the specified pose.
        :type goal_pose: geometry_msgs.msg.PoseStamped
        :return: RobotTrajectory (None if failed)
        """
        plan = generate_plan(self.group_left, goal_pose)
        if plan is None:
            return None
        self.left_arm_plan_publisher.publish(plan)
        return plan

    def execute_plan_right_arm(self, plan):
        """
        Executes the group_right plan movement, generated by plan_right_arm().
        :type plan: RobotTrajectory
        :return: Boolean indicating success.
        """
        return execute_plan(self.group_right, plan)

    def execute_plan_left_arm(self, plan):
        """
        Executes the group_left plan movement, generated by plan_left_arm().
        :type plan: RobotTrajectory
        :return: Boolean indicating success.
        """
        return execute_plan(self.group_left, plan)

    def generate_identity_plan(self, execute=False):
        """
        Generate a plan to move to the current pose - used to force joint state updates in unity.
        :return: moveit_msgs.msg.RobotTrajectory (None if failed)
        """
        pose = self.get_pose_right_arm()
        print 'target pose:', pose
        plan = self.generate_plan_right_arm(pose)
        if execute:
            print 'execute status:', self.execute_plan_right_arm(plan)
        return plan


def generate_pose_target(pose):
    """
    Takes in a pose and converts it to geometry_msgs.msg.PoseStamped
    :param pose: A list of 7 floats: (x,y,z,qx,qy,qz,qw)
    """
    assert len(pose) == 7  # assert 3 positions and 4 quaternions
    assert all(isinstance(c, float) for c in pose)  # assert pose contains only floats
    pose_target = geometry_msgs.msg.PoseStamped()
    pose_target.header.frame_id = '/base_link'
    pose_target.pose.position.x = pose[0]
    pose_target.pose.position.y = pose[1]
    pose_target.pose.position.z = pose[2]
    pose_target.pose.orientation.x = pose[3]
    pose_target.pose.orientation.y = pose[4]
    pose_target.pose.orientation.z = pose[5]
    pose_target.pose.orientation.w = pose[6]
    return pose_target


def generate_plan(group, goal_pose):
    """
    Moves the group ('left_arm' or 'right_arm') to goal_pose
    :return: RobotTrajectory (None if failed)
    :type group: moveit_commander.move_group.MoveGroupCommander
    :type goal_pose: geometry_msgs.msg.PoseStamped
    """
    assert isinstance(group, moveit_commander.move_group.MoveGroupCommander)
    assert isinstance(goal_pose, geometry_msgs.msg.PoseStamped)
    group.set_pose_target(goal_pose)
    plan = group.plan()
    if not plan.joint_trajectory.joint_names:  # empty list means failed plan
        print 'Plan failed! :('
        return None
    print 'plan:', plan
    return plan


def execute_plan(group, plan):
    """
    Execute the group's plan.
    :type group: moveit_commander.move_group.MoveGroupCommander
    :type plan: RobotTrajectory
    :return: A boolean indicating success of movement execution.
    """
    if plan is None:
        print 'No plan to execute!'
        return False
    assert isinstance(group, moveit_commander.move_group.MoveGroupCommander)
    assert isinstance(plan, RobotTrajectory)
    return group.execute(plan)


def identity_pose_request_callback(data):
    planHandler.generate_identity_plan(execute=True)


def sum_lists(lst1, lst2):
    return [x + y for x, y in zip(lst1, lst2)]


if __name__ == '__main__':
    rospy.Subscriber('/holocontrol/identity_pose_request', String, identity_pose_request_callback)
    planHandler = PlanHandler()
    p = planHandler.generate_identity_plan(execute=True)
    rospy.spin()
