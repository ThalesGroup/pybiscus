
from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclient import FlowerFabricClient
from pybiscus.interfaces.flower.clientfactory import ClientFactory


class FlowerFabricClientFactory(ClientFactory):

    def __init__(self,config,data,model,num_examples):
        self.config=config
        self.data=data
        self.model=model
        self.num_examples=num_examples

    def get_client(self):

        # print(f"@@@@@1 {self.config}")
        # print(f"@@@@@2 {self.config.client_run}")
        # print(f"@@@@@3 {self.config.client_run.cid}")

        return FlowerFabricClient(
            cid=self.config.client_run.cid,
            model=self.model,
            data=self.data,
            num_examples=self.num_examples,
            conf_fabric=self.config.client_compute_context.hardware,
            pre_train_val=self.config.client_run.pre_train_val,
        )
