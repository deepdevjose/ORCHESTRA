#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


class WeldingCellManager(Node):

    def __init__(self):
        super().__init__('welding_cell_manager')

        # Orden físico de las estaciones.
        # Las piezas avanzan en esta dirección:
        # r6 -> r3 -> r5 -> r2 -> r4 -> r1
        self.station_order = ['r6', 'r3', 'r5', 'r2', 'r4', 'r1']

        self.robots = ['r1', 'r2', 'r3', 'r4', 'r5', 'r6']

        self.joints_per_robot = [
            'joint_NAUO2',
            'joint_NAUO4',
            'joint_NAUO3',
            'joint_NAUO5',
            'joint_NAUO6',
            'joint_NAUO7'
        ]

        # ---------------------------------------------------------
        # POSICIONES
        # ---------------------------------------------------------

        # r1-r3
        self.HOME_R1_R3 = [3.8, 0.8, -1.5, 0.0, 0.0, 0.0]
        self.IDLE_R1_R3 = [1.6, 0.9, -1.0, 0.0, 0.0, 0.0]
        self.WELDING_UP_R1_R3 = [1.6, 0.0, 0.0, 1.0, 1.0, 0.0]
        self.WELDING_DOWN_R1_R3 = [1.6, -0.5, -0.3, 0.0, -1.0, 0.0]

        # r4-r6
        self.HOME_R4_R6 = [0.0, 0.8, -1.5, 0.0, 0.0, 0.0]
        self.IDLE_R4_R6 = [-1.6, 0.9, -1.0, 0.0, 0.0, 0.0]
        self.WELDING_UP_R4_R6 = [-1.6, 0.0, 0.0, 1.0, 1.0, 0.0]
        self.WELDING_DOWN_R4_R6 = [-1.6, -0.5, -0.3, 0.0, -1.0, 0.0]

        # ---------------------------------------------------------
        # CONFIGURACIÓN DE LA LÍNEA
        # ---------------------------------------------------------

        # Una pieza aparece cada 2 ciclos:
        # ciclo 1 -> pieza
        # ciclo 2 -> no pieza
        # ciclo 3 -> pieza
        # ciclo 4 -> no pieza
        # ...
        #
        # Cada ciclo representa el tiempo que tarda una pieza
        # en avanzar de una estación a la siguiente.
        self.cycle_time = 8.0

        # Tiempo que cada robot permanece soldando.
        self.welding_time = 6.0

        # Tiempo de movimiento de una trayectoria.
        self.motion_time = 1.0

        # Contador de ciclos de la línea.
        self.cycle_number = 0

        # ID de la siguiente pieza.
        self.next_piece_id = 1

        # Diccionario:
        # pieza_id -> estación
        #
        # Ejemplo:
        # {1: 2, 2: 1}
        #
        # significa:
        # pieza 1 está en r5
        # pieza 2 está en r3
        self.pieces = {}

        # Estado actual de cada robot.
        self.states = {
            robot: 'idle'
            for robot in self.robots
        }

        # Pieza que está siendo soldada por cada robot.
        self.robot_piece = {
            robot: None
            for robot in self.robots
        }

        # Mantenimiento.
        self.maintenance = {
            robot: False
            for robot in self.robots
        }

        # Alternancia de soldadura UP/DOWN por pieza.
        self.piece_welding_mode = {}

        # Timer de soldadura por robot.
        self.welding_timers = {}

        # ---------------------------------------------------------
        # ROS
        # ---------------------------------------------------------

        self.trajectory_pub = self.create_publisher(
            JointTrajectory,
            '/arm_controller/joint_trajectory',
            10
        )

        self.command_sub = self.create_subscription(
            String,
            '/welding_cell/command',
            self.command_callback,
            10
        )

        # Timer principal de la línea.
        self.line_timer = self.create_timer(
            self.cycle_time,
            self.advance_line
        )

        self.get_logger().info('==========================================')
        self.get_logger().info(' Welding Cell Manager iniciado')
        self.get_logger().info(' PIPELINE DE PRODUCCIÓN')
        self.get_logger().info(' Estaciones: r6 -> r3 -> r5 -> r2 -> r4 -> r1')
        self.get_logger().info(' Una pieza cada 2 ciclos')
        self.get_logger().info(' 5 segundos por ciclo')
        self.get_logger().info(' 2 segundos de soldadura')
        self.get_logger().info('==========================================')

        # Todos comienzan en IDLE.
        self.publish_all_states()

        # Primera pieza inmediatamente.
        self.spawn_piece()

    # =============================================================
    # LÓGICA DE LA LÍNEA
    # =============================================================

    def advance_line(self):
        """
        Avanza todas las piezas una estación.

        Ejemplo:

        Ciclo 1:
            pieza A -> r6

        Ciclo 2:
            pieza A -> r3

        Ciclo 3:
            pieza A -> r5
            pieza B -> r6

        Ciclo 4:
            pieza A -> r2
            pieza B -> r3

        etc.
        """

        self.cycle_number += 1

        self.get_logger().info(
            f'========== CICLO {self.cycle_number} =========='
        )

        # ---------------------------------------------------------
        # 1. Mover las piezas existentes a la siguiente estación.
        # ---------------------------------------------------------

        # Se procesa primero la última estación para evitar
        # conflictos al actualizar las posiciones.
        pieces_to_move = list(self.pieces.items())

        # Las piezas avanzan simultáneamente.
        new_positions = {}

        for piece_id, station_index in pieces_to_move:

            next_station = station_index + 1

            # La pieza salió de la línea.
            if next_station >= len(self.station_order):

                current_robot = self.station_order[station_index]

                if self.robot_piece[current_robot] == piece_id:
                    self.robot_piece[current_robot] = None

                self.get_logger().info(
                    f'Pieza {piece_id} terminó la línea y salió.'
                )

                continue

            new_positions[piece_id] = next_station

        self.pieces = new_positions

        # ---------------------------------------------------------
        # 2. Crear una nueva pieza cada 2 ciclos.
        # ---------------------------------------------------------

        if self.cycle_number % 2 == 1:
            self.spawn_piece()

        # ---------------------------------------------------------
        # 3. Actualizar qué pieza tiene cada robot.
        # ---------------------------------------------------------

        self.update_robot_assignments()

        # ---------------------------------------------------------
        # 4. Publicar posiciones.
        # ---------------------------------------------------------

        self.publish_all_states()

        self.print_line_status()

    def spawn_piece(self):
        """
        Inserta una pieza nueva en r6.
        """

        piece_id = self.next_piece_id
        self.next_piece_id += 1

        self.pieces[piece_id] = 0

        # Alternar UP/DOWN entre piezas.
        if piece_id % 2 == 1:
            self.piece_welding_mode[piece_id] = 'welding_up'
        else:
            self.piece_welding_mode[piece_id] = 'welding_down'

        self.get_logger().info(
            f'>>> Nueva pieza {piece_id} entra a la línea en r6 '
            f'({self.piece_welding_mode[piece_id]})'
        )

    def update_robot_assignments(self):
        """
        Determina qué robot tiene qué pieza.

        Un robot solamente trabaja si hay una pieza en su estación.
        Los demás permanecen en IDLE.
        """

        # Limpiar asignaciones.
        for robot in self.robots:
            self.robot_piece[robot] = None

        # Asignar piezas a robots.
        for piece_id, station_index in self.pieces.items():

            robot = self.station_order[station_index]

            # Si el robot está en mantenimiento, la pieza no puede
            # ser procesada por él.
            if self.maintenance[robot]:
                self.get_logger().warn(
                    f'Pieza {piece_id} llegó a {robot}, '
                    f'pero está en mantenimiento.'
                )
                continue

            self.robot_piece[robot] = piece_id

        # Actualizar estados.
        for robot in self.robots:

            if self.maintenance[robot]:
                self.states[robot] = 'home'
                continue

            piece_id = self.robot_piece[robot]

            if piece_id is None:
                self.states[robot] = 'idle'
            else:
                self.states[robot] = (
                    self.piece_welding_mode[piece_id]
                )

                self.start_welding_timer(
                    robot,
                    piece_id
                )

    # =============================================================
    # SOLDADURA
    # =============================================================

    def start_welding_timer(self, robot, piece_id):
        """
        Programa el regreso a IDLE después de la soldadura.

        El timer se reemplaza si ya existe uno para ese robot.
        """

        if robot in self.welding_timers:
            return

        timer = self.create_timer(
            self.welding_time,
            lambda r=robot, p=piece_id:
                self.finish_welding(r, p)
        )

        self.welding_timers[robot] = timer

    def finish_welding(self, robot, piece_id):
        """
        Termina visualmente la operación de soldadura.

        La pieza permanece en la estación hasta el siguiente
        ciclo de la línea.
        """

        timer = self.welding_timers.pop(robot, None)

        if timer is not None:
            timer.cancel()

        # Si la pieza sigue siendo la misma, el robot queda IDLE.
        if self.robot_piece[robot] == piece_id:

            if self.maintenance[robot]:
                self.states[robot] = 'home'
            else:
                self.states[robot] = 'idle'

            self.get_logger().info(
                f'{robot} terminó de soldar pieza {piece_id} -> IDLE'
            )

            self.publish_all_states()

    # =============================================================
    # MANTENIMIENTO
    # =============================================================

    def command_callback(self, msg):
        command = msg.data.strip().lower()

        # ---------------------------------------------------------
        # MANTENIMIENTO
        # ---------------------------------------------------------

        if command.startswith('mantenimiento_'):

            robot = command.replace(
                'mantenimiento_',
                ''
            )

            if robot not in self.robots:
                self.get_logger().warn(
                    f'Robot desconocido: {robot}'
                )
                return

            if self.maintenance[robot]:
                self.get_logger().warn(
                    f'{robot} ya está en mantenimiento.'
                )
                return

            self.maintenance[robot] = True
            self.states[robot] = 'home'

            # Cancelar timer de soldadura si existe.
            timer = self.welding_timers.pop(robot, None)

            if timer is not None:
                timer.cancel()

            self.get_logger().info(
                f'{robot} -> HOME / MANTENIMIENTO'
            )

            self.publish_all_states()

            return

        # ---------------------------------------------------------
        # ACTIVAR
        # ---------------------------------------------------------

        if command.startswith('activar_'):

            robot = command.replace(
                'activar_',
                ''
            )

            if robot not in self.robots:
                self.get_logger().warn(
                    f'Robot desconocido: {robot}'
                )
                return

            if not self.maintenance[robot]:
                self.get_logger().warn(
                    f'{robot} ya está activo.'
                )
                return

            self.maintenance[robot] = False
            self.states[robot] = 'idle'

            self.get_logger().info(
                f'{robot} -> ACTIVADO / IDLE'
            )

            # Si hay una pieza actualmente en su estación,
            # el robot puede comenzar a trabajar con ella.
            self.update_robot_assignments()

            self.publish_all_states()

            return

        self.get_logger().warn(
            f'Comando no reconocido: {command}'
        )

    # =============================================================
    # POSICIONES
    # =============================================================

    def get_robot_position(self, robot):

        robot_number = int(robot[1:])
        state = self.states[robot]

        if robot_number <= 3:

            if state == 'home':
                return self.HOME_R1_R3

            elif state == 'welding_up':
                return self.WELDING_UP_R1_R3

            elif state == 'welding_down':
                return self.WELDING_DOWN_R1_R3

            else:
                return self.IDLE_R1_R3

        else:

            if state == 'home':
                return self.HOME_R4_R6

            elif state == 'welding_up':
                return self.WELDING_UP_R4_R6

            elif state == 'welding_down':
                return self.WELDING_DOWN_R4_R6

            else:
                return self.IDLE_R4_R6

    # =============================================================
    # PUBLICACIÓN DEL TRAJECTORY
    # =============================================================

    def publish_all_states(self):

        msg = JointTrajectory()

        # Todos los robots se envían siempre al mismo controller.
        for robot in self.robots:

            for joint in self.joints_per_robot:
                msg.joint_names.append(
                    f'{robot}/{joint}'
                )

        point = JointTrajectoryPoint()

        for robot in self.robots:

            point.positions.extend(
                self.get_robot_position(robot)
            )

        point.time_from_start.sec = int(
            self.motion_time
        )

        point.time_from_start.nanosec = int(
            (self.motion_time % 1) * 1e9
        )

        msg.points.append(point)

        self.trajectory_pub.publish(msg)

    # =============================================================
    # INFORMACIÓN DE LA LÍNEA
    # =============================================================

    def print_line_status(self):

        status = []

        for robot in self.station_order:

            piece_id = self.robot_piece[robot]

            if self.maintenance[robot]:

                status.append(
                    f'{robot}: MAINTENANCE'
                )

            elif piece_id is None:

                status.append(
                    f'{robot}: IDLE'
                )

            else:

                status.append(
                    f'{robot}: PIEZA {piece_id} '
                    f'{self.states[robot].upper()}'
                )

        self.get_logger().info(
            ' | '.join(status)
        )


def main(args=None):

    rclpy.init(args=args)

    node = WeldingCellManager()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()