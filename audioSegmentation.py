import numpy, mlpy, time, scipy, os
import audioFeatureExtraction as aF
import audioTrainTest as aT
import matplotlib.pyplot as plt
from scipy.spatial import distance
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# # # # # # # # # # # # # # #
# General utility functions #
# # # # # # # # # # # # # # #

def smoothMovingAvg(inputSignal, windowLen=11):
	if inputSignal.ndim != 1:
		raise ValueError, ""
	if inputSignal.size < windowLen:
		raise ValueError, "Input vector needs to be bigger than window size."
	if windowLen<3:
		return x
	s = numpy.r_[2*inputSignal[0] - inputSignal[windowLen-1::-1], inputSignal, 2*inputSignal[-1]-inputSignal[-1:-windowLen:-1]]
	w = numpy.ones(windowLen, 'd')
	y = numpy.convolve(w/w.sum(), s, mode='same')
	return y[windowLen:-windowLen+1]

def selfSimilarityMatrix(featureVectors):
	'''
	ARGUMENTS:
	 - featureVectors: 	a numpy matrix (nDims x nVectors) whose i-th column corresponds to the i-th feature vector
	
	RETURNS:
	 - S:		 	the self-similarity matrix (nVectors x nVectors)
	'''

	[nDims, nVectors] = featureVectors.shape
	[featureVectors2, MEAN, STD] = aT.normalizeFeatures([featureVectors.T])
	featureVectors2 = featureVectors2[0].T
	S = 1.0 - distance.squareform(distance.pdist(featureVectors2.T, 'cosine'))
	return S

def flags2segs(Flags, window):
	'''
	ARGUMENTS:
	 - Flags: 	a sequence of class flags (per time window)
	 - window:	window duration (in seconds)
	
	RETURNS:
	 - segs:	a sequence of segment's endpoints: segs[i] is the endpoint of the i-th segment (in seconds)
	 - classes:	a sequence of class flags: class[i] is the class ID of the i-th segment
	'''

	preFlag = 0
	curFlag = 0
	numOfSegments = 0

	curVal = Flags[curFlag]
	segs = []
	classes = []
	while (curFlag<len(Flags)-1):
		stop = 0
	 	preFlag = curFlag
		preVal = curVal
	 	while (stop==0):
			curFlag = curFlag + 1
			tempVal = Flags[curFlag]
			if ((tempVal != curVal) | (curFlag==len(Flags)-1)): # stop
				numOfSegments = numOfSegments + 1
				stop = 1
				curSegment = curVal
				curVal = Flags[curFlag]
				segs.append((curFlag*window))
				classes.append(preVal)
	return (segs, classes)

def mtFileClassification(inputFile, modelName, modelType, plotResults = False):
	'''
	This function performs mid-term classification of an audio stream.
	Towards this end, supervised knowledge is used, i.e. a pre-trained classifier.
	ARGUMENTS:
		- inputFile:		path of the input WAV file
		- modelName:		name of the classification model
		- modelType:		svm or knn depending on the classifier type
		- plotResults:		True if results are to be plotted using matplotlib along with a set of statistics
	
	RETURNS:
	  	- segs:			a sequence of segment's endpoints: segs[i] is the endpoint of the i-th segment (in seconds)
		- classes:		a sequence of class flags: class[i] is the class ID of the i-th segment
	'''

	if not os.path.isfile(modelName):
		print "mtFileClassificationError: input modelType not found!"
		return (-1,-1)

	# Load classifier:
	if modelType=='svm':
		[Classifier, MEAN, STD, classNames, mtWin, mtStep, stWin, stStep] = aT.loadSVModel(modelName)
	elif modelType=='knn':
		[Classifier, MEAN, STD, classNames, mtWin, mtStep, stWin, stStep] = aT.loadKNNModel(modelName)
			
	[Fs, x] = aF.readAudioFile(inputFile)			# load input file
	if Fs == -1:						# could not read file
		return 
	x = aF.stereo2mono(x);					# convert stereo (if) to mono
	Duration = len(x) / Fs					
								# mid-term feature extraction:
	[MidTermFeatures, _] = aF.mtFeatureExtraction(x, Fs, mtWin * Fs, mtStep * Fs, round(Fs*stWin), round(Fs*stStep));
	flags = []; Ps = []; flagsInd = []
	for i in range(MidTermFeatures.shape[1]): 		# for each feature vector (i.e. for each fix-sized segment):
		curFV = (MidTermFeatures[:, i] - MEAN) / STD;	# normalize current feature vector					
		[Result, P] = aT.classifierWrapper(Classifier, modelType, curFV)	# classify vector
		flagsInd.append(Result)
		flags.append(classNames[int(Result)])		# update class label matrix
		Ps.append(numpy.max(P))				# update probability matrix

	(segs, classes) = flags2segs(flags, mtStep)		# convert fix-sized flags to segments and classes
	segs[-1] = len(x) / float(Fs)

	if plotResults:
		for i in range(len(classes)):
			if i==0:
				print "{0:3.1f} -- {1:3.1f} : {2:20s}".format(0.0, segs[i], classes[i])
			else:
				print "{0:3.1f} -- {1:3.1f} : {2:20s}".format(segs[i-1], segs[i], classes[i])

		# # # # # # # # # # # # 
		# Generate Statistics #
		# # # # # # # # # # # # 
		SPercentages = numpy.zeros((len(classNames), 1))
		Percentages = numpy.zeros((len(classNames), 1))
		AvDurations   = numpy.zeros((len(classNames), 1))

		for iSeg in range(len(segs)):
			if iSeg==0:
				SPercentages[classNames.index(classes[iSeg])] += (segs[iSeg])
			else:
				SPercentages[classNames.index(classes[iSeg])] += (segs[iSeg]-segs[iSeg-1])

		for i in range(SPercentages.shape[0]):
			Percentages[i] = 100.0*SPercentages[i] / Duration
			S = sum(1 for c in classes if c==classNames[i])
			if S>0:
				AvDurations[i] = SPercentages[i] / S
			else:
				AvDurations[i] = 0.0

		for i in range(Percentages.shape[0]):
			print classNames[i], Percentages[i], AvDurations[i]

		font = {'family' : 'fantasy', 'size'   : 10}
		plt.rc('font', **font)

		fig = plt.figure()	
		ax1 = fig.add_subplot(211)
		ax1.set_yticks(numpy.array(range(len(classNames))))
		ax1.axis((0, Duration, -1, len(classNames)))
		ax1.set_yticklabels(classNames)
		ax1.plot(numpy.array(range(len(flags)))*mtStep+mtStep/2.0, flagsInd)
		plt.xlabel("time (seconds)")

		ax2 = fig.add_subplot(223)
		plt.title("Classes percentage durations")
		ax2.axis((0, len(classNames)+1, 0, 100))
		ax2.set_xticks(numpy.array(range(len(classNames)+1)))
		ax2.set_xticklabels([" "] + classNames)
		ax2.bar(numpy.array(range(len(classNames)))+0.5, Percentages)

		ax3 = fig.add_subplot(224)
		plt.title("Segment average duration per class")
		ax3.axis((0, len(classNames)+1, 0, AvDurations.max()))
		ax3.set_xticks(numpy.array(range(len(classNames)+1)))
		ax3.set_xticklabels([" "] + classNames)
		ax3.bar(numpy.array(range(len(classNames)))+0.5, AvDurations)
		fig.tight_layout()
		plt.show()

	return (segs, classes)


def speechSegmentation(x, Fs, midTermSize, midTermStep, plot = False):
	'''
	NOTE: UNUSED! EMBED IN SPEAKER DIARIZATION OR REMOVE
	speechSegmentation(x, Fs, midTermSize, midTermStep, plot = False)
	
	This function is used to segment a speech signal. 
	ARGUMENTS:
		x:		the speech signal samples
		Fs:		sampling freq
		midTermSize:	++++
	'''
	stWindow = 0.10
	x = aF.stereo2mono(x);
	# STEP A: extract mid and short-term features:
	[MidTermFeatures, ShortTermFeatures] = aF.mtFeatureExtraction(x, Fs, midTermSize * Fs, midTermStep * Fs, round(Fs*stWindow), round(Fs*stWindow));

	# STEP B: 
	# keep only the energy short-term sequence (2nd feature)	
	EnergySt = ShortTermFeatures[1, :]
	# sort energy feature values:
	E = numpy.sort(EnergySt)
	L1 = int(len(E)/10)
	# compute "lower" energy threshold ...
	T1 = numpy.mean(E[0:L1])
	# ... and "higher" energy threhold:
	T2 = numpy.mean(E[-L1:-1])
	# get the whole short-term feature vectors for the respective two classes (low energy and high energy):
	Class1 = ShortTermFeatures[:,numpy.where(EnergySt<T1)[0]]
	Class2 = ShortTermFeatures[:,numpy.where(EnergySt>T2)[0]]
	# form the binary classification task and train the respective SVM probabilistic model
	featuresSS = [Class1.T, Class2.T];
	[featuresNormSS, MEANSS, STDSS] = aT.normalizeFeatures(featuresSS)
	SVM = aT.trainSVM(featuresNormSS, 1.0)

	Pspeech = []
	# compute and smooth the Speech probability:
	for i in range(ShortTermFeatures.shape[1]):
		curFV = (ShortTermFeatures[:,i] - MEANSS) / STDSS
		Pspeech.append(SVM.pred_probability(curFV)[1])
	Pspeech = numpy.array(Pspeech)
	Pspeech = smoothMovingAvg(smoothMovingAvg(Pspeech, 3), 5)
	# get the "valley" positions of the speech probability sequence:
	MinIdx = numpy.where(Pspeech<0.4)[0];
	i = 0;
	timeClusters = []
	while i<len(MinIdx):
		curCluster = [MinIdx[i]]
		if i==len(MinIdx)-1:
			break		
		while MinIdx[i+1] - curCluster[-1] <= 2:
			curCluster.append(MinIdx[i+1])
			i += 1
			if i==len(MinIdx)-1:
				break
		i += 1
		timeClusters.append(curCluster)

	Mins = []
	for c in timeClusters:
		Mins.append(numpy.mean(c))		

	# transform the positions to time (seconds)
	segmentLimits = numpy.array([0.0])
	segmentLimits = numpy.append(segmentLimits, numpy.array(Mins) * stWindow)
	segmentLimits = numpy.append(segmentLimits, len(x)/float(Fs))

	# print numpy.array(Mins) * stWindow
	if plot:
		plt.subplot(2,1,1); plt.plot(x)
		for l in Mins:
			plt.axvline(x=l*Fs*stWindow); 
		plt.subplot(2,1,2); plt.plot(Pspeech);
		for l in Mins:
			plt.axvline(x=l); 
		plt.show()

	return segmentLimits


def speakerDiarization(x, Fs, mtSize, mtStep):
	numOfSpeakers = 4;
	x = aF.stereo2mono(x);
	Duration = len(x) / Fs
	[MidTermFeatures, ShortTermFeatures] = aF.mtFeatureExtraction(x, Fs, mtSize * Fs, mtStep * Fs, round(Fs*0.040), round(Fs*0.020));
	(MidTermFeaturesNorm, MEAN, STD) = aT.normalizeFeatures([MidTermFeatures.T])	
	MidTermFeaturesNorm = MidTermFeaturesNorm[0].T
	cls, means, steps = mlpy.kmeans(MidTermFeaturesNorm.T, k=numOfSpeakers, plus=True)	
	print cls
	print means.shape
	print MidTermFeaturesNorm.shape

	# compute confidence (TODO)
	Y = distance.cdist(MidTermFeaturesNorm.T, means, 'euclidean')	
	print Y.shape
	#for i in range(MidTermFeaturesNorm.shape[1]):	# for each mid-term window:		
		#print Y

	classNames = ["speaker{0:d}".format(c) for c in range(numOfSpeakers)];
	fig = plt.figure()	
	ax1 = fig.add_subplot(111)
	ax1.set_yticks(numpy.array(range(len(classNames))))
	ax1.axis((0, Duration, -1, len(classNames)))
	ax1.set_yticklabels(classNames)
	ax1.plot(numpy.array(range(len(cls)))*mtStep+mtStep/2.0, cls)
	plt.xlabel("time (seconds)")
	plt.show()


def musicThumbnailing(x, Fs, shortTermSize=1.0, shortTermStep=0.5, thumbnailSize=10.0):
	'''
	This function detects instances of the most representative part of a music recording, also called "music thumbnails".
	A technique similar to the one proposed in [1], however a wider set of audio features is used instead of chroma features.
	In particular the following steps are followed:
	 - Extract short-term audio features. Typical short-term window size: 1 second
	 - Compute the self-silimarity matrix, i.e. all pairwise similarities between feature vectors
 	 - Apply a diagonal mask is as a moving average filter on the values of the self-similarty matrix. 
	   The size of the mask is equal to the desirable thumbnail length.
 	 - Find the position of the maximum value of the new (filtered) self-similarity matrix.
	   The audio segments that correspond to the diagonial around that position are the selected thumbnails
	

	ARGUMENTS:
	 - x:			input signal
	 - Fs:			sampling frequency
	 - shortTermSize: 	window size (in seconds)
	 - shortTermStep:	window step (in seconds)
	 - thumbnailSize:	desider thumbnail size (in seconds)
	
	RETURNS:
	 - A1:			beginning of 1st thumbnail (in seconds)
	 - A2:			ending of 1st thumbnail (in seconds)
	 - B1:			beginning of 2nd thumbnail (in seconds)
	 - B2:			ending of 2nd thumbnail (in seconds)

	USAGE EXAMPLE:
  	 import audioFeatureExtraction as aF
	 [Fs, x] = aF.readAudioFile(inputFile)
	 [A1, A2, B1, B2] = musicThumbnailing(x, Fs)

	[1] Bartsch, M. A., & Wakefield, G. H. (2005). Audio thumbnailing of popular music using chroma-based representations. 
	Multimedia, IEEE Transactions on, 7(1), 96-104.
	'''
	x = aF.stereo2mono(x);
	# feature extraction:
	stFeatures = aF.stFeatureExtraction(x, Fs, Fs*shortTermSize, Fs*shortTermStep)

	# self-similarity matrix
	S = selfSimilarityMatrix(stFeatures)

	# moving filter:
	M = round(thumbnailSize / shortTermStep)
	B = numpy.eye(M,M)
	S = scipy.signal.convolve2d(S, B, 'valid')

	# post-processing (remove main diagonal elements)
	MIN = numpy.min(S)
	for i in range(S.shape[0]):
		for j in range(S.shape[1]):
			if abs(i-j) < 2.0 / shortTermStep:
				S[i,j] = MIN;

	# find max position:
	maxVal = numpy.max(S)
	I = numpy.argmax(S)
	[I, J] = numpy.unravel_index(S.argmax(), S.shape)

	# expand:
	i1 = I; i2 = I
	j1 = J; j2 = J
	while i2-i1<M:
		if S[i1-1, j1-1] > S[i2+1,j2+1]:
			i1 -= 1
			j1 -= 1
		else:
			i2 += 1
			j2 += 1
	
	return (shortTermStep*i1, shortTermStep*i2, shortTermStep*j1, shortTermStep*j2)