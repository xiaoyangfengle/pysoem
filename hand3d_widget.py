from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *

class Hand3DWidget(QOpenGLWidget):
    def __init__(self):
        super().__init__()
        self.joint_angles = [0.0 for _ in range(20)]

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.2, 0.2, 0.2, 1.0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, w / h if h != 0 else 1, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluLookAt(0, 20, 60, 0, 0, 0, 0, 1, 0)

        self.draw_palm()

        for i, angle in enumerate(self.joint_angles):
            glPushMatrix()
            base_x = -8 + (i % 5) * 4
            base_y = 0
            base_z = -5 + (i // 5) * 10

            glTranslatef(base_x, base_y, base_z)
            glRotatef(angle, 1, 0, 0)
            glColor3f(0.7, 0.9, 1.0)
            self.draw_finger()
            glPopMatrix()

    def draw_palm(self):
        glPushMatrix()
        glTranslatef(0, -2, 0)
        glScalef(10, 1, 4)
        self.draw_cube()
        glPopMatrix()

    def draw_finger(self):
        glBegin(GL_QUADS)
        glVertex3f(-0.5, 0, -0.5)
        glVertex3f( 0.5, 0, -0.5)
        glVertex3f( 0.5, 4, -0.5)
        glVertex3f(-0.5, 4, -0.5)

        glVertex3f(-0.5, 0,  0.5)
        glVertex3f( 0.5, 0,  0.5)
        glVertex3f( 0.5, 4,  0.5)
        glVertex3f(-0.5, 4,  0.5)

        glVertex3f(-0.5, 0, -0.5)
        glVertex3f(-0.5, 0,  0.5)
        glVertex3f(-0.5, 4,  0.5)
        glVertex3f(-0.5, 4, -0.5)

        glVertex3f(0.5, 0, -0.5)
        glVertex3f(0.5, 0,  0.5)
        glVertex3f(0.5, 4,  0.5)
        glVertex3f(0.5, 4, -0.5)

        glVertex3f(-0.5, 4, -0.5)
        glVertex3f( 0.5, 4, -0.5)
        glVertex3f( 0.5, 4,  0.5)
        glVertex3f(-0.5, 4,  0.5)

        glVertex3f(-0.5, 0, -0.5)
        glVertex3f( 0.5, 0, -0.5)
        glVertex3f( 0.5, 0,  0.5)
        glVertex3f(-0.5, 0,  0.5)
        glEnd()

    def draw_cube(self):
        vertices = [
            [-0.5, -0.5, -0.5],
            [ 0.5, -0.5, -0.5],
            [ 0.5,  0.5, -0.5],
            [-0.5,  0.5, -0.5],
            [-0.5, -0.5,  0.5],
            [ 0.5, -0.5,  0.5],
            [ 0.5,  0.5,  0.5],
            [-0.5,  0.5,  0.5],
        ]
        faces = [
            [0, 1, 2, 3],
            [1, 5, 6, 2],
            [5, 4, 7, 6],
            [4, 0, 3, 7],
            [3, 2, 6, 7],
            [4, 5, 1, 0],
        ]
        glBegin(GL_QUADS)
        for face in faces:
            for vertex in face:
                glVertex3fv(vertices[vertex])
        glEnd()

    def set_joint_angle(self, finger_idx, angle):
        if 0 <= finger_idx < len(self.joint_angles):
            self.joint_angles[finger_idx] = angle
            self.update()
