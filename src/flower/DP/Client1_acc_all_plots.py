import matplotlib.pyplot as plt

# Vos données
x_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
client1_dp_False= [0.9002,0.9712 ,0.9796 ,  0.9834, 0.9864 , 0.9876 ,0.9901 ,0.9909 ,0.9916 , 0.9919]
client1_dp_True_1= [0.6179, 0.7562, 0.7369,0.7459 ,0.7348 ,0.7411 ,0.7482,0.7362 , 0.7455,0.7258 ] 
client1_dp_True_2=  [0.1608, 0.1080,0.1042 ,0.1100 , 0.1096,0.1096 , 0.1056, 0.1134, 0.1061,0.1041 ]
client1_dp_True_3=[0.6903, 0.8827, 0.8984, 0.9012, 0.8980,  0.8956,0.8988 ,0.8940 , 0.9009, 0.9011]
client1_dp_True_4=[0.6682, 0.8520 , 0.8585 ,0.8572 , 0.8420, 0.8424 , 0.8510 , 0.8401,0.8517 , 0.8588]
client1_dp_True_5=[0.6999,0.8985, 0.9175, 0.9251,0.9275 ,0.9317 , 0.9352,  0.9354, 0.9394, 0.9425]

#PS: client1_dp_True_1: delta=1e-5 and noise=1.1  
   # client1_dp_True_2: delta=1e-5 and noise=4;
   # client1_dp_True_3: delta=1e-5 and noise=0.5
   # client1_dp_True_4: delta=1e-5 and noise=0.7
   # client1_dp_True_5: delta=1e-5 and noise=0.3

   


# Tracer le graphique

plt.plot(x_values, client1_dp_False,color="#d62728", label='No Privacy')
plt.plot(x_values, client1_dp_True_5,linestyle='dashed',color="#1bc45155", label='With DP: noise=0.3, Epsilon=223.16')
plt.plot(x_values, client1_dp_True_3,linestyle='dashed',color="#f07e0c55", label='With DP: noise=0.5, Epsilon=44.45')
plt.plot(x_values, client1_dp_True_4,linestyle='dashed',color="#f0f00c55", label='With DP: noise=0.7, Epsilon=16.75')
plt.plot(x_values, client1_dp_True_1,linestyle='dashed',color="#b327d655", label='With DP: noise=1.1, Epsilon=5.31')
plt.plot(x_values, client1_dp_True_2,linestyle='dashed',color="#2736d655", label='With DP: noise=4, Epsilon=1.05')

plt.xlabel('Rounds')
plt.ylabel('Accuracy')
plt.title("Client1 validation accuracy with and without DP on Mnist with CNN")
plt.legend()
x_ticks = [x for x in x_values if x % 2 == 0] 
plt.xticks(x_ticks)
# Enregistrer le graphique
plt.savefig('client1_acc_all.png', dpi=300)
plt.show()
