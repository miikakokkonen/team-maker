
from PyQt5.QtCore import pyqtSlot, QTimer, Qt
from PyQt5.QtWidgets import QDialog, QApplication, QFileDialog, QLabel, QProgressBar, QTableWidgetItem, QStyledItemDelegate# QPushButton, QTableWidget, QComboBox, QLabel, QTabWidget, QStackedWidget
from PyQt5.uic import loadUi
from PyQt5.QtGui import QBrush, QMouseEvent
from sys import argv, exit
from multiprocessing import Process, cpu_count, Queue, Array, freeze_support
from requests import get as rget
from random import shuffle
from itertools import product
from math import sqrt


class Player():
	def __init__(self, name, mmr, roles, btag, sc= ''):
		self.name = name
		self.mmr = mmr
		self.roles = roles
		if sc:
			sc='X'
		self.sc = 'X'
		self.btag = btag
		self.mmrdelta = 0
		self.adjusted = False
		self.iterable = [self.name, self.getmmr(), self.roles, self.sc]

	def __repr__(self):
		return(' '.join([self.name,str(self.getmmr()), self.roles, self.sc]))
	
	def __iter__(self):
		self.n=0
		return self

	def __getitem__(self, index):
		return self.iterable[index]

	def __setitem__(self, index, value):
		self[index] = value

	def __next__(self):
		if self.n<=3:
			result = self[self.n]
			self.n += 1
			return(result)
		else:
			raise StopIteration

	def getmmr(self):
		if self.adjusted == True:
			return self.mmr+self.mmrdelta
		return self.mmr


class ShuffleProcess(Process):
	def __init__(self,all_players,q,progress,pindex,amount,use_sc,roleval):
		Process.__init__(self)
		all_players = sorted(all_players, key= lambda x: x[1], reverse=1)
		self.shuffle(all_players,q,progress,pindex,amount,use_sc,roleval)
	def shuffle(self,all_players,q,progress,pindex,amount,use_shotcaller,roleval):
		
		def stats(somelist):
			n = len(somelist)
			m2,e2=0,0
			for d in somelist:
				m2 += d ** 2
				e2 += d
			mean = e2/n
			m2 = m2/n
			e2 = mean**2
			std = sqrt(m2-e2)
			return mean,std

		players = len(all_players)
		teams = players//5
		possibilities = [[[999, 999, 999, '', '', 999], [] ]]
		if use_shotcaller:
			all_players = sorted(all_players, key= lambda x: x[3], reverse = 1)
		top_players = all_players[0:teams]
		bot_players = all_players[teams:]
		rolevalues = {'T':int(8*roleval), 'S':int(4*roleval), 'O':int(2*roleval), 'A':int(1*roleval)}
		y = 0.005
		for prog in range(amount):
			teamlists = [ [] for _ in range(teams)]
			shuffle(bot_players)
			if prog/amount >=y:
				y+=0.005
				progress[pindex] = int(y*1000)
			i_bot_players = iter(bot_players)
			for i in range(teams):
				teamlists[i].append(top_players[i])
				teamlists[i].extend([next(i_bot_players) for _ in range(4)])
			rolecheck = [0 for _ in range(teams)]
			for i in range(teams):
				roles = [ [x for x in y[2]] for y in teamlists[i]]
				for x in product(*roles):
					v = sum([rolevalues[y] for y in set(x)])
					if v > rolecheck[i]:
						rolecheck[i] = v
			rolepoints = sum(rolecheck)/len(rolecheck)
			test = teamlists
			iter_test = iter(test)
			results = []
			for _ in range(teams):
				test_players = next(iter_test)
				test_avg, test_std = stats([play.getmmr() for play in test_players])
				results.append([test_avg, test_std])
			total_avg, avg_points = stats([i for i,_ in results])
			std_avg_points, std_std_points = stats([j for _,j in results])
			std_avg_points /=5 
			if possibilities[-1][0][0] + possibilities[-1][0][1] + possibilities[-1][0][2] - possibilities[-1][0][5] > avg_points + std_avg_points + std_std_points - rolepoints**2:
				possibilities.append([[avg_points, std_avg_points, std_std_points, results, rolecheck, rolepoints**2], test])
		if len(possibilities) >1:
			q.put(possibilities[-1])
		if len(possibilities) > 2:
			q.put(possibilities[-2])
		if len(possibilities) > 3:
			q.put(possibilities[-3])
	


class HotslogsProcess(Process):
	def __init__(self,playerlist,responseq):
		Process.__init__(self)
		self.responseq = responseq
		self.playerlist = playerlist
		self.startprocess()

	def startprocess(self):
		for i,p in self.playerlist:
			json_response = rget(''.join(['https://api.hotslogs.com/Public/Players/2/',p.btag.replace('#','_')])).json()
			d = []
			if json_response is not None:
				for j in [1,2,3,0]:
					try:
					
						if json_response['LeaderboardRankings'][j]['LeagueRank']:
							d.append([j,json_response['LeaderboardRankings'][j]['CurrentMMR']])
					except:
						pass
					if len(d) ==2:
						break
				if len(d) != 0:
					p.mmrdelta = (sum([a[1] for a in d])//len(d))-p.mmr
				else:
					p.mmrdelta = 0
			self.responseq.put([i,p.mmrdelta])

class TeamWindow(QDialog):

	def __init__(self):
		super().__init__()
		self.ui = loadUi('teamwindow.ui',self)
		self.loadplayersprogressBar.hide()
		self.tabWidget.setCurrentIndex(0)
		self.updatinglabel.hide()
		self.updating = False
		self.playerlist = []
		self.use_sc = False
		self.currentsort = ['mmr', False]
		self.amount = 100000
		self.roleval = 3
		self.tablelist = [self.tableWidget_1, self.tableWidget_2, self.tableWidget_3, self.tableWidget_4, self.tableWidget_5, self.tableWidget_6, self.tableWidget_7, self.tableWidget_8]
		self.tbrowserlist = [self.t1Browser, self.t2Browser, self.t3Browser, self.t4Browser, self.t5Browser, self.t6Browser, self.t7Browser, self.t8Browser, self.t9Browser]
		self.sortinglist = [self.namesortButton, self.mmrsortButton, self.mmrdeltasortButton, self.rolessortButton, self.scsortButton]
		self.buttonlist = [self.rerollButton, self.loadplayersButton, self.adjustButton, self.removeadjustmentButton, self.selectallButton]
		self.comboboxlist = [self.variationscomboBox]
		self.spinboxes = [self.processesspinBox, self.amountspinBox, self.rolevalspinBox]
		self.processes = 0
		self.sccheckBox.stateChanged.connect(lambda x: self.change_sc())
		
		for table in self.tablelist:
			for i in range(3):
				table.setColumnWidth(i,134)
				table.setSizeAdjustPolicy(0)
			table.setAttribute(Qt.WA_TransparentForMouseEvents,True)
		for browser in self.tbrowserlist:
			table.setAttribute(Qt.WA_TransparentForMouseEvents,True)
		for spinbox in self.spinboxes:
			spinbox.valueChanged.connect(lambda x: setattr(self,self.sender().objectName()[:-7:],x))
		for sortbutton in self.sortinglist:
			sortbutton.clicked.connect(lambda: self.changesorting(self.sender().objectName()))
		for combobox in self.comboboxlist:
			combobox.currentTextChanged.connect(lambda: getattr(self,self.sender().objectName()+'OnChange')())
		for button in self.buttonlist:
			button.clicked.connect(lambda: getattr(self,self.sender().objectName()+'Clicked')())
		
		cores = cpu_count()
		self.processes = cores//2
		self.processesspinBox.setMaximum(cores)
		self.processesspinBox.setValue(cores//2)
		self.recommendedlabel.setText(''.join(['(',str(cores//2),' recommended',')']))

	@pyqtSlot()
	def change_sc(self):
		self.use_sc = not self.use_sc
		self.sclistWidget.clear()
		if self.use_sc:
			for i,t in enumerate(self.tablelist):
				t.insertColumn(3)
				t.setHorizontalHeaderItem(3,QTableWidgetItem('sc'))
				for i in range(3):
					t.horizontalHeader().resizeSection(i,120)
				t.horizontalHeader().resizeSection(3,42)
			for i,p in enumerate(self.playerlist):
				self.sclistWidget.addItem(p.sc)
			if hasattr(self,'results'):
				self.setvalues(self.variationscomboBox.currentIndex())
		else:
			for i,t in enumerate(self.tablelist):
				t.removeColumn(3)
				for i in range(3):
					t.horizontalHeader().resizeSection(i,134)

	@pyqtSlot()
	def changesorting(self,x):
		if self.updating:
			return
		if self.currentsort[0] == x[:-10:]:
			self.currentsort[1] = not self.currentsort[1]
		else:
			self.currentsort[0] = x[:-10:]
		self.resort()

	@pyqtSlot()
	def rerollButtonClicked(self):
		if self.updating:
			return
		self.updating = True
		self.q = Queue()
		self.progress = Array('i',[0]*self.processes)
		self.shuffleprocesslist = []
		for pindex in range(self.processes):
			p = Process(target = ShuffleProcess, args = (self.playerlist, self.q, self.progress, pindex, self.amount, self.use_sc, self.roleval), daemon = True)
			p.start()
			self.shuffleprocesslist.append(p)
		self.createprogressbars()
		self.ptimer = QTimer(self)
		self.ptimer.setTimerType(Qt.PreciseTimer)
		self.ptimer.timeout.connect(self.updateprogressbars)
		self.ptimer.start(200)

	def createprogressbars(self):
		self.tabWidget.setCurrentIndex(0)
		x,y = 540,30
		self.pblabels = []
		self.pbs = []
		for i in range(self.processes):
			l = QLabel(self.tabWidget.children()[0])
			self.pblabels.append(l)
			l.setText('CORE'+str(i))
			l.setGeometry(x,y+50*i,50,13)
			
			pb = QProgressBar(self.tabWidget.children()[0])
			self.pbs.append(pb)
			pb.setValue(0)
			pb.setGeometry(x,y+20+50*i,200,15)
			if self.tabWidget.currentIndex()==0:
				l.show()
				pb.show()

	
	def updateprogressbars(self):
		proge = [(a/10) for a in self.progress[:]]
		for i,pb in enumerate(self.pbs):
			pb.setValue(proge[i])
		if self.progress[:] == [1000]*self.processes:
			self.ptimer.stop()
			for l,pb in zip(self.pblabels,self.pbs):
				l.setParent(None)
				pb.setParent(None)

			self.getvalues()

	def getvalues(self):
		self.results = []
		while not self.q.empty():
			retval = self.q.get()
			self.results.append(retval)
		for process in self.shuffleprocesslist:
			try:
				process.terminate()
			except:
				pass
		variation=0
		self.variationscomboBox.clear()
		for i in range(len(self.results)):
			self.variationscomboBox.addItem(str(i+1))
		self.variationscomboBox.setCurrentIndex(0)
		self.results = sorted(self.results, key = lambda x: sum(x[0][0:3]))
		self.setvalues(variation)
		self.updating=False

	def setvalues(self,variation):
		for table in self.tablelist:
			table.clearContents()
		if len(self.results) == 1:
			self.results = [self.results]
		if self.results:
			result = self.results[variation]
			score_stats='POINTS:'+str(int(result[0][0]+result[0][1]+result[0][2]))+'\n\nAVGSTD:'+str(int(result[0][0]))+'\n\nSTDAVG:'+str(int(result[0][1]))+'\n\nSTDSTD:'+str(int(result[0][2]))+'\n\n(pienempi=parempi)'
			self.t9Browser.setText(score_stats)
			for i, team in enumerate(result[1]):
				form = 'MMR AVG: {}'+' '*79+'VARIATION: {}'
				form = form.format(*[int(val) for val in result[0][3][i] ])
				self.tbrowserlist[i].setText(form)
				team = sorted(team, key= lambda x: x[1], reverse=1)
				for j,player in enumerate(team):
					for k,item in enumerate(player):
						if k==3:
							if self.use_sc:
								self.tablelist[i].setItem(j,k,QTableWidgetItem(str(item)))
								pass
							else:
								continue
						if k==1:
							self.tablelist[i].setItem(j,k,QTableWidgetItem(str(player.getmmr())))
						else:
							self.tablelist[i].setItem(j,k,QTableWidgetItem(str(item)))

		
	@pyqtSlot()
	def loadplayersButtonClicked(self):
		if self.updating:
			return
		self.updating = True
		self.updatinglabel.show()
		self.loadplayersprogressBar.show()
		dlg = QFileDialog()
		dlg.setFileMode(QFileDialog.AnyFile)
		if dlg.exec_():
			filenames = dlg.selectedFiles()[0]
			if filenames[-1:-4:-1] == 'txt':
				with open(filenames,'r') as f:
					content = f.read()
				self.playerlist = [player.split('\t') for player in content.split('\n') if len(player)>0]
				print(self.playerlist)
				self.playerlist = sorted(	[Player(	name.split('#')[0], int(mmr), ''.join(sorted([r[0] for r in roles.split(', ')], reverse = 1)), name, *sc) for name, mmr, roles, *sc in self.playerlist], key = lambda x: x.mmr, reverse = 1)
				print(self.playerlist)
				self.playeramount = len(self.playerlist)
				self.namelistWidget.clear(), self.mmrlistWidget.clear(), self.mmrdeltalistWidget.clear(), self.roleslistWidget.clear(), self.sclistWidget.clear()
				self.playeramounttextBrowser.setText(str(len(self.playerlist)))
				self.responseq = Queue()
				ep = [[i,p] for i,p in enumerate(self.playerlist)]
				p1 = ep[:(self.playeramount)//2]
				p2 = ep[self.playeramount//2:]
				self.loadprogress = 0
				self.hotslogsprocess1 = Process(target = HotslogsProcess, args= (p1, self.responseq), daemon=True).start()
				self.hotslogsprocess2 = Process(target = HotslogsProcess, args= (p2, self.responseq), daemon=True).start()

				for i,p in enumerate(self.playerlist):
					self.namelistWidget.addItem(p.name), self.mmrlistWidget.addItem(str(p.getmmr())),self.mmrdeltalistWidget.addItem(str(p.mmrdelta)),self.roleslistWidget.addItem(p.roles)
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.gray))
				self.adjusttimer = QTimer(self)
				self.adjusttimer.setTimerType(Qt.PreciseTimer)
				self.adjusttimer.timeout.connect(self.adjustmmrdeltas)
				self.adjusttimer.start(1000)
		else:
			self.updatinglabel.hide()
			self.loadplayersprogressBar.hide()
			self.updating=False

	@pyqtSlot()
	def adjustButtonClicked(self):
		for i in [x.row() for x in self.namelistWidget.selectedIndexes()]:
			if self.playerlist[i].adjusted == False:
				self.playerlist[i].adjusted = True
				self.mmrlistWidget.item(i).setText(str(self.playerlist[i].getmmr()))
				try:
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.darkYellow))
					self.mmrlistWidget.item(i).setForeground(QBrush(Qt.darkBlue))
				except:
					pass

	@pyqtSlot()
	def removeadjustmentButtonClicked(self):
		for i in [x.row() for x in self.namelistWidget.selectedIndexes()]:
			if self.playerlist[i].adjusted == True:
				self.playerlist[i].adjusted = False
				self.mmrlistWidget.item(i).setText(str(self.playerlist[i].getmmr()))
				try:
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.gray))
					self.mmrlistWidget.item(i).setForeground(QBrush(Qt.black))
				except:
					pass

	@pyqtSlot()
	def selectallButtonClicked(self):
		self.namelistWidget.selectAll()

	@pyqtSlot()
	def variationscomboBoxOnChange(self):
		self.setvalues(self.variationscomboBox.currentIndex())

	def adjustmmrdeltas(self):
		while not self.responseq.empty():
			i,p = self.responseq.get()
			self.loadprogress += 1/self.playeramount
			self.loadplayersprogressBar.setValue(int(self.loadprogress*100))
			self.playerlist[i].mmrdelta = p
			self.mmrdeltalistWidget.item(i).setText(str(p))
			self.mmrlistWidget.item(i).setText(str(self.playerlist[i].getmmr()))
			try:
				if self.playerlist[i].adjusted:
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.darkYellow))
					self.mmrlistWidget.item(i).setForeground(QBrush(Qt.darkBlue))
				else:
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.gray))
			except:
				pass
			if i==self.playeramount-1:
				self.updatinglabel.hide()
				self.loadplayersprogressBar.hide()
				self.updating = False
				self.adjusttimer.stop()
				try:
					self.hotslogsprocess1.terminate()
					self.hotslogsprocess2.terminate()
				except:
					pass
				return True

	def resort(self):
		sortcolumn, sortreverse = self.currentsort
		if sortcolumn == 'name':
			self.playerlist = sorted(self.playerlist, key= lambda x: getattr(x,sortcolumn).lower(), reverse = sortreverse)
		elif sortcolumn == 'roles':
			self.playerlist = sorted(sorted(self.playerlist, key = lambda x: getattr(x,sortcolumn), reverse = 1), key= lambda x: len(getattr(x,sortcolumn)), reverse = sortreverse)
		elif sortcolumn == 'mmr':
			self.playerlist = sorted(self.playerlist, key= lambda x: getattr(x,'getmmr')(), reverse = sortreverse)
		elif sortcolumn == 'sc':
			self.playerlist = sorted(self.playerlist, key= lambda x: len(getattr(x,sortcolumn)), reverse = sortreverse)
		else:
			self.playerlist = sorted(self.playerlist, key= lambda x: x.mmrdelta, reverse = sortreverse)

		self.namelistWidget.clear(), self.mmrlistWidget.clear(), self.mmrdeltalistWidget.clear(), self.roleslistWidget.clear(), self.sclistWidget.clear()
		for i,p in enumerate(self.playerlist):
			self.namelistWidget.addItem(p.name), self.mmrlistWidget.addItem(str(p.getmmr())),self.mmrdeltalistWidget.addItem(str(p.mmrdelta)),self.roleslistWidget.addItem(p.roles)
			if self.use_sc:
				self.sclistWidget.addItem(p.sc)
			try:
				if self.playerlist[i].adjusted:
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.darkYellow))
					self.mmrlistWidget.item(i).setForeground(QBrush(Qt.darkBlue))
				else:
					self.mmrdeltalistWidget.item(i).setForeground(QBrush(Qt.gray))
			except:
				pass


if __name__ == '__main__':
	freeze_support()
	app = QApplication(argv)
	window = TeamWindow()
	window.setWindowTitle('Team maker')
	window.show()
	exit(app.exec_())