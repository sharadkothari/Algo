from data_loader import DataLoader
from chart import Chart

d = DataLoader(1)
d.by_option = True

d.load_data()
d.spread.live = True
c = Chart(d)
fig = c.plot()
fig.show()