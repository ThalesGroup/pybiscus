import matplotlib.pyplot as plt

# Vos données
x_values = [0,1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
server_dp_False= [0.09130000323057175, 0.9711999893188477, 0.9828000068664551, 0.9876999855041504, 0.9871000051498413, 0.9901000261306763, 0.9894999861717224, 0.9908999800682068, 0.9889000058174133, 0.9901999831199646, 0.9908999800682068]
server_dp_True_1=  [0.09130000323057175, 0.7404999732971191, 0.7793999910354614, 0.7577000260353088, 0.7397000193595886, 0.756600022315979, 0.7506999969482422, 0.7735000252723694, 0.7577000260353088, 0.7459999918937683, 0.7257999777793884]
server_dp_True_2=  [0.09130000323057175, 0.10639999806880951, 0.10779999941587448, 0.11230000108480453, 0.10369999706745148, 0.11299999803304672, 0.09849999845027924, 0.13009999692440033, 0.11819999665021896, 0.10419999808073044, 0.10170000046491623]
server_dp_True_3=[0.09130000323057175, 0.8593999743461609, 0.9103999733924866, 0.917900025844574, 0.9103000164031982, 0.9103999733924866, 0.9156000018119812, 0.9061999917030334, 0.9063000082969666, 0.909600019454956, 0.9078999757766724]
server_dp_True_4=[0.09130000323057175, 0.8335000276565552, 0.879800021648407, 0.8769000172615051, 0.8659999966621399, 0.8557000160217285, 0.870199978351593, 0.8637999892234802, 0.8482999801635742, 0.8705999851226807, 0.871399998664856]
server_dp_True_5= [0.09130000323057175, 0.8845000267028809, 0.9225999712944031, 0.9319000244140625, 0.9369000196456909, 0.9384999871253967, 0.9430999755859375, 0.9430000185966492, 0.9429000020027161, 0.9451000094413757, 0.9474999904632568]

#PS: server_dp_True_1: delta=1e-5 and noise=1.1  
   # server_dp_True_2: delta=1e-5 and noise=4;
   # server_dp_True_3: delta=1e-5 and noise=0.5
   # server_dp_True_4: delta=1e-5 and noise=0.7
   # server_dp_True_5: delta=1e-5 and noise=0.3

   


# Tracer le graphique

plt.plot(x_values, server_dp_False,color="#d62728", label='No Privacy')
plt.plot(x_values, server_dp_True_5,linestyle='dashed',color="#1bc45155", label='With DP: noise=0.3, Epsilon=223.16')
plt.plot(x_values, server_dp_True_3,linestyle='dashed',color="#f07e0c55", label='With DP: noise=0.5, Epsilon=44.45')
plt.plot(x_values, server_dp_True_4,linestyle='dashed',color="#f0f00c55", label='With DP: noise=0.7, Epsilon=16.75')
plt.plot(x_values, server_dp_True_1,linestyle='dashed',color="#b327d655", label='With DP: noise=1.1, Epsilon=5.31')
plt.plot(x_values, server_dp_True_2,linestyle='dashed',color="#2736d655", label='With DP: noise=4, Epsilon=1.05')

plt.xlabel('Rounds')
plt.ylabel('Accuracy')
plt.title("Server test accuracy with and without DP on Mnist with CNN")
plt.legend()
x_ticks = [x for x in x_values if x % 2 == 0] 
plt.xticks(x_ticks)
# Enregistrer le graphique
plt.savefig('acc_all.png', dpi=300)
plt.show()
