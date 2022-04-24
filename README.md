# Python-Modbus-
Implementation of a Controller acts as Modbus Master, Execution of Logic as Function depending on XML data base 

Modbus layer is being handled by PyModbus library 

the control is based on Function Block Logic (Function Block Language) all FB will executed in order. 

the data based is based on XML file, which has all the configuration ( 

  - Defining Devices ( IP, Port) 
  - Defining Modbus setting to used. 
  - Defining the control module to be executed  ( Customizatoin of Control Module (CM) should be done in XML file) 
        # CM_Details = { 'CM_Name1' : {'AI1' : { 'Type' : 'AI', 'Ex_Order' : 1, 'Parm1' : 0, 'IO_IN' : 'E1_TEST3' , 'Input_Ref' : None}, \
        #                              'AO1' : { 'Type' : 'AO', 'Ex_Order' : 1, 'Parm1' : 0, 'IO_IN' : 'E1_TEST1', 'Input_Ref' : {'IN1_cv' : {'AI1': 'out_cv'}} } }}
        # CM_Details = { 'CM_Name1' : {'AI1' : { 'Type' : 'AI', 'Ex_Order' : 1, 'Parm1' : 0, 'IO_IN' : 'E1_TEST3' , 'Input_Ref' : None}, \
        #                              'AO1' : { 'Type' : 'AO', 'Ex_Order' : 1, 'Parm1' : 0, 'IO_IN' : 'E1_TEST1', 'Input_Ref' : {'IN1_cv' : {'AI1': 'out_cv'}} } }}
        
  - Defining Global Parameters 
you can setup a data base to store all historic data (not fully tested) 

Web Interface with API to control and Mointor

