import json
import math
import numpy as np

from Structures import STRUCTURES


class NET(STRUCTURES):
    '''
    Parameters
    ----------

    '''
    
    def __init__(self, name, filename, OCEAN, lat_node, lon_node):

        
        with open(filename, 'r') as load_f:
            params_dict = json.load(load_f)

        self.cable_strength = params_dict["NET"]["ClCable"]
        self.cable_diameter = params_dict["NET"]["DiameterCable"]
        self.lat_numass_per_length = params_dict["NET"]["MassPerMCable"]
        self.density = params_dict["NET"]["MaterialDensity"]
        self.intertia_coeff = params_dict["NET"]["InertiaCoefficient"]
        self.half_len = params_dict["NET"]["lambda"]

        self.__cal_const_var(lat_node, lon_node)
        self.__init_element(np.asarray(lat_node), np.asarray(lon_node))

        super().__init__(OCEAN, name, 1)

        print("NET instance is built.")

    # =======================================
    # 計算網片相關常數
    # =======================================
    def __cal_const_var(self, lat_node, lon_node):

        self.lat_num = len(lat_node[0,:])-1 #横向
        self.lon_num = len(lon_node[0,:])-1 #縱向

        self.num_node = (self.lat_num+1)*(self.lon_num+1)
        self.num_element = self.lon_num*(self.lat_num+1) + self.lat_num*(self.lon_num+1)
        self.num_net_mesh = self.lat_num*self.lon_num
 
    # =======================================
    # 計算初始網片構件(兩端)質點位置、速度
    # =======================================
    def __init_element(self, lat_node, lon_node):

        # global position, velocity, force of nodes
        self.global_node_position = np.zeros((3, self.num_node))
        self.global_node_velocity = np.zeros((3, self.num_node))
        self.pass_force = np.zeros((3,self.num_node))

        node_index = 0
        for i in range(self.lon_num+1):
            if i == 0:
                lon_vector = np.zeros(3)
            else:
                lon_vector += lon_node[:,i] - lon_node[:,i-1]

            for j in range(self.lat_num+1):
                if j == 0:
                    lat_vector = np.zeros(3)
                else:
                    lat_vector += lat_node[:,j] - lat_node[:,j-1]

                self.global_node_position[:, node_index] = (lat_node[:,0] + lat_vector + lon_vector)
                
                node_index += 1


        self.origin_length = np.zeros(self.num_element)

        for i in range(self.num_element):
            node_index = self.get_node_index(i)
            self.origin_length[i] = np.linalg.norm(self.global_node_position[:, node_index[0]]-
                                                   self.global_node_position[:, node_index[1]] )
        
        self.net_mesh_line_lat = np.zeros(self.num_net_mesh)
        self.net_mesh_line_lon = np.zeros(self.num_net_mesh)
        self.Sn = np.zeros(self.num_net_mesh)
        self.net_mesh_area = np.zeros(self.num_net_mesh)
        self.net_mesh_volume = np.zeros(self.num_net_mesh)
        self.net_mesh_mass = np.zeros(self.num_net_mesh)

        for i in range(self.num_net_mesh):
            node_index = self.get_node_index(i, source='net_mesh')

            self.net_mesh_line_lat[i] = np.linalg.norm(self.global_node_position[:, node_index[0]]-
                                                   self.global_node_position[:, node_index[1]] )/self.half_len
            
            self.net_mesh_line_lon[i] =  np.linalg.norm(self.global_node_position[:, node_index[0]]-
                                                   self.global_node_position[:, node_index[3]] )/self.half_len

            # 計算固相比
            self.Sn[i] = 2*(self.cable_diameter/self.half_len)+0.5*(self.cable_diameter/self.half_len)**2

            # 計算每個element網面的面積
            vec1 = self.global_node_position[:, node_index[1]]- self.global_node_position[:, node_index[0]]
            vec2 = self.global_node_position[:, node_index[3]]- self.global_node_position[:, node_index[0]]
            self.net_mesh_area[i] = np.linalg.norm(np.cross(vec1,vec2))

            # 計算每個element網面的體積	   
            self.net_mesh_volume[i] = ( np.pi*(self.cable_diameter/2)**2 
                                    *(self.net_mesh_line_lat[i]* np.linalg.norm(vec1)
                                     +self.net_mesh_line_lon[i]* np.linalg.norm(vec2)) )

            # 計算每個element網面的質量
            self.net_mesh_mass[i]  = self.net_mesh_volume[i] *self.density

    # =======================================
    # Runge Kutta 4th 更新質點位置
    # =======================================
    def update_position_velocity(self, dt):
        
        for connection in self.connections:
            if connection["connect_obj_node_condition"] == 1:
                self.new_rk4_position[:,connection["self_node"]] = connection["connect_obj"].global_node_position[:,connection['connect_obj_node']]
                self.new_rk4_velocity[:,connection["self_node"]] = connection["connect_obj"].global_node_velocity[:,connection['connect_obj_node']]
            
            elif connection["self_node_condition"] == 1:
                connection["connect_obj"].global_node_position[:,connection['connect_obj_node']] = self.new_rk4_position[:,connection["self_node"]]
                connection["connect_obj"].global_node_velocity[:,connection['connect_obj_node']] = self.new_rk4_velocity[:,connection["self_node"]]

        self.global_node_position = np.copy(self.new_rk4_position)
        self.global_node_velocity = np.copy(self.new_rk4_velocity)

    # =======================================
    # 計算質點位置、速度
    # =======================================  
    def cal_node_pos_vel(self, global_node_position_temp, global_node_velocity_temp):
        
        self.global_node_position = global_node_position_temp
        self.global_node_velocity = global_node_velocity_temp
        
        for connection in self.connections:
            if connection["connect_obj_node_condition"] == 1:
                self.global_node_position[:,connection["self_node"]] = connection["connect_obj"].global_node_position[:,connection['connect_obj_node']]
                self.global_node_velocity[:,connection["self_node"]] = connection["connect_obj"].global_node_velocity[:,connection['connect_obj_node']]
            
            elif connection["self_node_condition"] == 1:
                connection["connect_obj"].global_node_position[:,connection['connect_obj_node']] = self.global_node_position[:,connection["self_node"]]
                connection["connect_obj"].global_node_velocity[:,connection['connect_obj_node']] = self.global_node_velocity[:,connection["self_node"]]

    # =======================================
    # 計算構件受力
    # =======================================
    def cal_element_force(self, present_time):
        
        # 初始化流阻力、慣性力、浮力、重力、附加質量
        self.flow_resistance_force =  np.zeros((3,self.num_net_mesh))
        self.inertial_force =  np.zeros((3,self.num_net_mesh))
        self.buoyancy_force =  np.zeros((3,self.num_net_mesh))
        self.gravity_force =  np.zeros((3,self.num_net_mesh))
        self.tension_force = np.zeros((3,self.num_element))
        self.added_mass_element = np.zeros(self.num_net_mesh)
        
        # 初始化外傳力
        self.pass_force = np.zeros((3,self.num_node))


        for i in range(self.num_net_mesh):
            
            node_index = self.get_node_index(i, source = "net_mesh")
            tri_index = [0,0,0]   

            for tri_num in range(2):
                
                if tri_num == 0:
                    tri_index[0] = node_index[0]
                    tri_index[1] = node_index[1]
                    tri_index[2] = node_index[2] 
                elif tri_num == 1:
                    tri_index[0] = node_index[2]
                    tri_index[1] = node_index[3]
                    tri_index[2] = node_index[0]

                # 計算三角形三邊向量
                vec12 = self.global_node_position[:, tri_index[1]] -self.global_node_position[:, tri_index[0]]
                vec23 = self.global_node_position[:, tri_index[2]] -self.global_node_position[:, tri_index[1]]
                vec31 = self.global_node_position[:, tri_index[0]] -self.global_node_position[:, tri_index[2]]
                
                # 計算三角形三邊邊長
                tri_length12 = np.linalg.norm(vec12)
                tri_length23 = np.linalg.norm(vec23)
                tri_length31 = np.linalg.norm(vec31)

                # 計算面積
                dc = (tri_length12+tri_length23+tri_length31)/2.  	#周長/2
                tri_area = np.sqrt(np.abs(dc*(dc-tri_length12)*(dc-tri_length23)*(dc-tri_length31)))     #海龍公式


                # 計算三角形所在面的單位法
                # vec12 cross vec23 /abs(vec12*vec23)
                cross = np.zeros(3)
                cross[0] = vec12[1]*vec23[2]-vec12[2]*vec23[1]
                cross[1] = vec12[2]*vec23[0]-vec12[0]*vec23[2]
                cross[2] = vec12[0]*vec23[1]-vec12[1]*vec23[0]
                

                abscro = np.linalg.norm(cross)

                if(abscro == 0):
                    en = np.zeros(3)
                else:
                    en =cross /abscro
                    
                absen = np.linalg.norm(en)

                # 三角形形心
                tri_cg_position = (( self.global_node_position[:,tri_index[0]] +
                                     self.global_node_position[:,tri_index[1]] +
                                     self.global_node_position[:,tri_index[2]] ) /3 ) 
            
                # 構件(三角)質心處海波流場
                water_velocity, water_acceleration = self.OCEAN.cal_wave_field( tri_cg_position[0],
                                                                                tri_cg_position[1],
                                                                                tri_cg_position[2],
                                                                                present_time )
                
                # 計算流與網面的夾角
                if((absen*np.linalg.norm(water_velocity) == 0)):
                    afa = 0
                else:
                    afa = np.arccos((en[0]*water_velocity[0]+
                                     en[1]*water_velocity[1]+
                                     en[2]*water_velocity[2])/(absen*np.linalg.norm(water_velocity)))
                
                if (afa >= 0.5*np.pi) :
                    afa=np.pi-afa
 

                # 流阻力係數  Loland經驗公式	
                cd_net = 0.04+(-0.04+0.33*self.Sn[i]+6.54*self.Sn[i]**2-4.88*self.Sn[i]**3)*np.cos(afa)
                cd_lift = (-0.05*self.Sn[i]+2.3*self.Sn[i]**2-1.76*self.Sn[i]**3)*np.sin(2*afa)
                
                # 構件(三角)速度
                tri_vel =  (( self.global_node_velocity[:,tri_index[0]] +
                              self.global_node_velocity[:,tri_index[1]] +
                              self.global_node_velocity[:,tri_index[2]]) /3 )


                tri_vel_abs = np.linalg.norm( tri_vel ) 
                
                # 網面的單位相對速度向量
                relative_velocity = water_velocity - tri_vel
                relative_velocity_abs = np.linalg.norm(relative_velocity)

                if relative_velocity_abs == 0:
                    relative_velocity_unit = np.zeros(3)
                else:
                    relative_velocity_unit = relative_velocity / relative_velocity_abs
                
                relative_velocity__unit_abs = np.linalg.norm(relative_velocity_unit) 
                
                # !!  el :　lift force　方向
                # !===el =(eu x en) x eu / | (eu x en) x eu|  =====
                e_lift = np.zeros(3)
                e_lift[0] = (relative_velocity_unit[2]*en[0]-relative_velocity_unit[0]*en[2])*relative_velocity_unit[2]-(relative_velocity_unit[0]*en[1]-relative_velocity_unit[1]*en[0])*relative_velocity_unit[1]
                e_lift[1] = (relative_velocity_unit[0]*en[1]-relative_velocity_unit[1]*en[0])*relative_velocity_unit[0]-(relative_velocity_unit[1]*en[2]-relative_velocity_unit[2]*en[1])*relative_velocity_unit[2]
                e_lift[2] = (relative_velocity_unit[1]*en[2]-relative_velocity_unit[2]*en[1])*relative_velocity_unit[1]-(relative_velocity_unit[2]*en[0]-relative_velocity_unit[0]*en[2])*relative_velocity_unit[0]
                
                e_lift_abs = np.linalg.norm(e_lift) 

                # normalize
                if e_lift_abs == 0:
                    e_lift = np.zeros(3)
                else:
                    e_lift = e_lift / e_lift_abs

                # ===判斷el方向 acos(eu .dot. en) > pi/2  el=-el === (for背流面，因為網片的法線向量恆指向網袋內)
                if ( np.arccos( relative_velocity_unit.dot(en)) > np.pi/2):
                    e_lift = -e_lift

                tri_area_projection = abs(tri_area*(relative_velocity_unit.dot(en)))
                # 流阻力 (計算切線及法線方向流阻力分量)
                flow_resistance_force_tang =  0.5*self.OCEAN.water_density*cd_net*tri_area_projection*relative_velocity_abs**2*relative_velocity_unit
                flow_resistance_force_lift =  0.5*self.OCEAN.water_density*cd_lift*tri_area_projection*relative_velocity_abs**2*e_lift 


                self.flow_resistance_force[:, i] += (flow_resistance_force_tang + flow_resistance_force_lift)
               

                # 慣性力
                self.inertial_force[:, i] += self.OCEAN.water_density*self.intertia_coeff*self.net_mesh_volume[i]*0.5*water_acceleration


                if ( np.linalg.norm(water_acceleration) != 0):
                    self.added_mass_element[i] += 0.5*(self.intertia_coeff-1)*self.OCEAN.water_density*self.net_mesh_volume[i]*0.5
                else:
                    self.added_mass_element[i] += 0


                # 浮力
                self.buoyancy_force[:, i] += np.asarray([  0,
                                                           0,
                                                           self.OCEAN.water_density*self.net_mesh_volume[i]*0.5*self.OCEAN.gravity])

                
                # 重力
                self.gravity_force[:, i] += np.asarray([   0,
                                                           0, 
                                                           -self.net_mesh_mass[i]*self.OCEAN.gravity*0.5])

        # 張力    
        for i in range(self.num_element):

            net_mesh_index = self.from_element_get_net_mesh_index(i)
            node_index = self.get_node_index(i)

            # 構件切線向量
            element_tang_vecotr =  [ self.global_node_position[0, node_index[1]] - self.global_node_position[0, node_index[0]],
                                     self.global_node_position[1, node_index[1]] - self.global_node_position[1, node_index[0]],
                                     self.global_node_position[2, node_index[1]] - self.global_node_position[2, node_index[0]] ]

            element_length = np.linalg.norm(element_tang_vecotr)
            element_tang_unitvector = element_tang_vecotr / element_length

            epsolon = (element_length - self.origin_length[i] ) / self.origin_length[i]


            if epsolon > 0:
                if i < self.lat_num or i >= (self.num_element - self.lat_num):
                    self.tension_force[:, i] = 0.5*self.net_mesh_line_lat[net_mesh_index[0]]*(0.25*math.pi*self.cable_diameter**2)*self.cable_strength*epsolon*self.OCEAN.gravity*element_tang_unitvector

                elif len(net_mesh_index) == 1:
                    self.tension_force[:, i] = 0.5*self.net_mesh_line_lon[net_mesh_index[0]]*(0.25*math.pi*self.cable_diameter**2)*self.cable_strength*epsolon*self.OCEAN.gravity*element_tang_unitvector

                elif (i+1) % (2*self.lat_num + 1) <= self.lat_num:
                    num_line = self.net_mesh_line_lat[net_mesh_index[0]] + self.net_mesh_line_lat[net_mesh_index[1]]
                    self.tension_force[:, i] = 0.5*num_line*(0.25*math.pi*self.cable_diameter**2)*self.cable_strength*epsolon*self.OCEAN.gravity*element_tang_unitvector

                else:
                    num_line = self.net_mesh_line_lon[net_mesh_index[0]] + self.net_mesh_line_lon[net_mesh_index[1]]
                    self.tension_force[:, i] = 0.5*num_line*(0.25*math.pi*self.cable_diameter**2)*self.cable_strength*epsolon*self.OCEAN.gravity*element_tang_unitvector

            else:
                self.tension_force[:, i] = np.zeros(3)


       # 計算外傳力
        for i in range(self.num_node):

            net_index = self.get_net_mesh_index(i)
            element_index = self.get_element_index(i)

            # 網面上
            for index in net_index:
                self.pass_force[:, i] += (    
                                            self.flow_resistance_force[:, index]
                                            + self.inertial_force[:, index]
                                            + self.buoyancy_force[:, index]                                  
                                            + self.gravity_force[:, index] 
                                            )/4

            # 構件上
            if i == self.lat_num:
                sign = -1
                for index in element_index:
                    self.pass_force[:, i] += sign*self.tension_force[:, index]
                    sign = sign*(-1)

            elif i == (self.num_node - 1 - self.lat_num):
                sign = -1
                for index in element_index:
                    self.pass_force[:, i] += sign*self.tension_force[:, index]
                    sign = sign*(-1)

            elif i == (self.num_node-1):   
                for index in element_index:
                    self.pass_force[:, i] += -self.tension_force[:, index]

            elif i == 0 :   
                for index in element_index:
                    self.pass_force[:, i] += self.tension_force[:, index]
            
            elif i <= self.lat_num: 
                sign =[-1, 1, 1]
                sign_index = 0  
                for index in element_index:
                    self.pass_force[:, i] += sign[sign_index]*self.tension_force[:, index]
                    sign_index =  sign_index + 1

            elif i >= self.num_node - self.lat_num: 
                sign =[1, -1, 1]
                sign_index = 0  
                for index in element_index:
                    self.pass_force[:, i] += sign[sign_index]*self.tension_force[:, index]
                    sign_index =  sign_index + 1

            elif (i+1) % (self.lat_num+1) == 1 : 
                sign =[-1, 1, 1]
                sign_index = 0  
                for index in element_index:
                    self.pass_force[:, i] += sign[sign_index]*self.tension_force[:, index]
                    sign_index =  sign_index + 1
                     
            elif (i+1) % (self.lat_num+1) == 0 :   
                sign =[-1, -1, 1]
                sign_index = 0  
                for index in element_index:
                    self.pass_force[:, i] += sign[sign_index]*self.tension_force[:, index]
                    sign_index =  sign_index + 1
            else:
                sign =[ -1, -1, 1, 1]
                sign_index = 0  
                for index in element_index:
                    self.pass_force[:, i] += sign[sign_index]*self.tension_force[:, index]
                    sign_index =  sign_index + 1

    # =======================================
    # 計算回傳速度、加速度
    # =======================================
    def cal_vel_acc(self):

        self.node_force = np.zeros((3,self.num_node))
        node_mass = np.zeros(self.num_node)
        global_node_acc_temp = np.zeros((3,self.num_node))
        connected_force = np.zeros((3,self.num_node))


        # 連結力
        for connection in self.connections:
            if connection["self_node_condition"] == 1:
                connected_force[:, connection["self_node"]] += connection["connect_obj"].pass_force[:,connection['connect_obj_node']]



        # 質點總合力
        for i in range(self.num_node):

            net_index = self.get_net_mesh_index(i)

            for index in net_index:
                node_mass[i] += ( self.net_mesh_mass[index] + self.added_mass_element[index] )/4

            self.node_force[:,i] = self.pass_force[:,i] + connected_force[:,i]

  
            if (node_mass[i] == 0):
                global_node_acc_temp[:,i] = 0
            else:
                global_node_acc_temp[:,i] = self.node_force[:,i]/node_mass[i]


        global_node_velocity_temp = np.copy(self.global_node_velocity)

        return global_node_velocity_temp, global_node_acc_temp
    # =======================================
    # 質點 構件 關係
    # =======================================

    def get_node_index(self, element_number, source = 'element'):

        # 找element相關點
        if source == 'element':

            element_num = np.copy(element_number)
            origin_num = element_number % ( 2*self.lat_num + 1) 
            increasement = 0
            while element_num >= 0:

                if origin_num < self.lat_num:
                    node_index =  [ origin_num + increasement,
                                    origin_num + increasement+ 1]

                else:
                    node_index =  [ origin_num + increasement - self.lat_num,
                                    origin_num + increasement + 1]
                                    

                increasement += self.lat_num + 1

                element_num = element_num - (2*self.lat_num + 1)

        # 找net mesh相關點
        elif source == 'net_mesh':
            element_num = np.copy(element_number)
            origin_num = element_number % self.lat_num
            increasement = 0
            while element_num >= 0:

                node_index =  [ origin_num + increasement,
                                origin_num + increasement + 1,
                                origin_num + increasement + self.lat_num + 2,
                                origin_num + increasement + self.lat_num + 1 ]

                increasement += self.lat_num + 1
                element_num = element_num - self.lat_num

        return node_index


    def get_element_index(self, node_number):

        element_index = []

        for i in range(self.num_element):
            if node_number in self.get_node_index(i):
                element_index.append(i)

        return element_index


    def get_net_mesh_index(self, node_number):

        element_index = []

        for i in range(self.num_net_mesh):
            if node_number in self.get_node_index(i, source='net_mesh'):
                element_index.append(i)

        return element_index


    def from_element_get_net_mesh_index(self, element_number):

        if element_number < self.lat_num:
            net_mesh_index = [element_number]

        elif element_number >= self.num_element - self.lat_num:
            net_mesh_index = [self.num_net_mesh - self.num_element + element_number]

        else:
            element_num = np.copy(element_number)

            origin_num = element_number % ( 2*self.lat_num + 1) 
            increasement = 0

            while element_num >= 0:

                if origin_num == self.lat_num:
                    net_mesh_index =  [ origin_num - self.lat_num + increasement]
  
                elif origin_num == 2*self.lat_num:
                    net_mesh_index =  [ origin_num - self.lat_num + increasement -1]

                elif origin_num < self.lat_num:
                    net_mesh_index =  [ origin_num + increasement - self.lat_num,
                                        origin_num + increasement]

                else:
                    net_mesh_index =  [ origin_num - self.lat_num + increasement-1,
                                        origin_num - self.lat_num + increasement]
            

                increasement += self.lat_num
                element_num = element_num - (2*self.lat_num + 1)

        return net_mesh_index




if __name__ == "__main__":
     pass
