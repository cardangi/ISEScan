import sys
import argparse
import operator
import csv
import time
import random
import os
import datetime
import itertools
import math
import concurrent.futures
import tempfile

# required by clusterIntersect()
import scipy.spatial.distance
import numpy, fastcluster
import scipy.cluster.hierarchy

import tools
import is_analysis
import constants


# re-rank hmmsearch hits by 4 (full sequence E-value, default ranking of hmmsearch results) or 0 (best 1 domain E-value)
SORT_BY = 4


# process_tblout(tblout):
# > Sort hits by ov, best 1 domain E-value and full sequence E-value
# > Remove unsatisfying hits based on ov, best 1 domain E-value and full sequence E-value
#
# Return hits
#
# hits: [hit, ...]
# hit: [best1domainEvalue, line, compoundID, queryName, best1domainEvalue, overlapNumber]
# best1domainEvalue: float, evalue for best 1 domain, refer to hmmsearch manual for details
# line: whole line ending with '\n' in hmmhitsFile created by hmmsearch
# compoundID: the first string ending with space character in protein sequence (.faa) file 
#	created by FragGeneScan, e.g. 'gi|256374160|ref|NC_013093.1|_6781872_6782144_-', 
#	'SRS078176_LANL_scaffold_27612_1219_2391_-', 'C2308936_1_1062_-'
# queryName: name of HMM model in profile HMM model file created by hmmsearch or phmmer, 
#	e.g. 'IS200_IS605_0.faa', 'IS200/IS605_1|IS200/IS605|IS1341|ISBLO15|'
# overlap: integer, overlap number, how many of envelopes overlap other envelopes; 
#	be careful when ov > 0refer to hmmsearch manual for details
#
def process_tblout(tblout):
	hits = []
	fp_tblout = open(tblout, 'r')
	for line in fp_tblout:
		if line[0] == '#':
			continue
		item = line.split(None, 14)
		# item[0]: string, compound ID, for example, 'gi|256374160|ref|NC_013093.1|_6781872_6782144_-',
		#	'SRS078176_LANL_scaffold_27612_1219_2391_-', 'C2308936_1_1062_-'
		# item[2]: query name, name of query sequence or profile (IS cluster name), for example,
		#		'IS200_IS605_0.faa', 'IS200/IS605_1|IS200/IS605|IS1341|ISBLO15|'
		# item[4]: full sequence E-value
		# item[7]: best 1 domain E-value
		# item[13]: overlap number, how many of envelopes overlap other envelopes; 
		#	be careful when ov > 0

		# remove short ORF with length < length of shortest peptide in ISfinder
		'''
		if '.faa' in item[2]:
			familyCluster = item[2].rsplit('.faa', maxsplit=1)[0]
		elif '|' in item[2]:
			familyCluster = item[2].split('|', maxsplit=1)[0]
		else:
			e = 'Error, unknown query name in output of Hmmer (hmmsearch/phmmer) in '.format(tblout)
			raise RuntimeError(e)
		familyCluster = familyCluster.replace('IS200_IS605', 'IS200/IS605')
		family, cluster = familyCluster.split('_', maxsplit=1)
		minLen4orf4pep = constants.minMax4tpase[family][2]
		orfbd = [int(x) for x in item[0].rsplit('_',3)[-3:-1]]
		if orfbd[1] - orfbd[0] + 1 < minLen4orf4pep:
			continue
		'''

		#
		#hits.append((float(item[7]), line, item[0], item[2].replace('IS200_IS605', 'IS200/IS605'), float(item[4]), int(item[13])))
		#
		# FORCE PIPELINE TO PREDICT IS BASED ON BEST 1 DOMAIN e-VALUE.
		#
		hits.append((float(item[7]), line, item[0], item[2].replace('IS200_IS605', 'IS200/IS605'), float(item[7]), int(item[13])))
		#
		# hits: [hit, ...]
		# hit: [best1domainEvalue, line, compoundID, queryName, best1domainEvalue, overlapNumber]
		# best1domainEvalue: float, evalue for best 1 domain, refer to hmmsearch manual for details
		# line: whole line ending with '\n' in hmmhitsFile created by hmmsearch or phmmer
		# compoundID: the first string ending with space character in protein sequence (.faa) file 
		#	created by FragGeneScan, e.g. 'gi|256374160|ref|NC_013093.1|_6781872_6782144_-',
		#	'C2308936_1_1062_-', 'SRS078176_LANL_scaffold_9132_3106_4113_+'
		# queryName: name of HMM model in profile HMM model file created by hmmsearch or phmmer, 
		#	e.g. 'IS200_IS605_0.faa', 'IS200/IS605_1|IS200/IS605|IS1341|ISBLO15|'
		# overlap: integer, overlap number, how many of envelopes overlap other envelopes; 
		#	be careful when ov > 0refer to hmmsearch manual for details

	fp_tblout.close()
	return hits

	'''
	# Sort hits
	# If sorted type is changed here, please change e_value_type in 
	# refine_hmm_hits_evalue(tblout_hits_sorted, e_value) immediately
	#
	# 5 , 0 and 4 correspond to overlap number, best 1 domain E-value and full sequence E-value, respectively
	if SORT_BY == 0:
		hits_sorted = sorted(hits, key = operator.itemgetter(0))
	elif SORT_BY == 4:
		# hmmsearch report hits ranked by full sequence E-value for each HMM model.
		# We rank hits from all HMM modles in one hmmsearch report file in one sorting.
		# Note: mutliple family HMM models exist in each tbl_out file, see any tbl_out file
		# refer to ftp://selab.janelia.org/pub/software/hmmer3/3.1b2/Userguide.pdf
		hits_sorted = sorted(hits, key = operator.itemgetter(4))

	# Do not sort hits, namely, keeping the ranking (by full sequence E-value) reported by hmmsearch
	# Note: each HMM model hits have their own ranking in the same tbl_out report file.
	#hits_sorted = hits

	# hits_sorted: [hit, ..., hit]
	# hit[0]: float, best 1 domain E-value
	# hit[1]: string, whole line
	# hit[2]: string, compound ID, for example, 'gi|256374160|ref|NC_013093.1|_6781872_6782144_-',
	#	'C2308936_1_1062_-', 'SRS078176_LANL_scaffold_9132_3106_4113_+'
	# hit[3]: string, IS family name
	# hit[4]: float, full sequence E-value
	# hit[5]: int, overlap number, how many of envelopes overlap other envelopes; be careful when ov > 0
	#accid = hits_sorted[0][2].rsplit('|', 2)[-2]
	#seqid = hits_sorted[0][2].rsplit('_', 3)[0]
	seqids = set()
	# seqids: {}, set of sequence identifiers in a dnaFile with multiple sequences included
	for hit in hits_sorted:
		seqid = hits_sorted[0][2].rsplit('_', 3)[0]
		seqids.add(seqid)

	return (seqids, hits_sorted)
	'''


# refine_hmm_hits() removes the redundant hits (same genome location hitted by different family HMM models) 
# and keeps only the best one (sorted by ov and E-values) 
# among the hits mapped to the same genome coordinate pair.
# In our hmmsearch results,
# each hit is from a different profile HMM search against the same protein database, 
# where each IS family HMM model was used once to search the same protein database.
# Note: two hits are identical or redundant if their coordinates with ignoring strand
#	in genome DNA are same. This idea is to coordinate with the definition of IS elements
#	where IS element is a genome DNA segment without dependence to the specific DNA strand.
#
# mtblout_hits_sorted: a sorted hits list
def refine_hmm_hits(tblout_hits_sorted):
	hits_refined = []
	coord_key = []
	for hit in tblout_hits_sorted:
		# hit[2]: string, compound ID, 
		#	for example, 'gi|15896971|ref|NC_002754.1|_1734599_1736514_+', 'ref|U00096.3|_3720680_3722049_+'
		# coord: '_1734599_1736514_+', '_3720680_3722049_+'
		# 
		#coord = (hit[2].rsplit('|', 1))[-1]
		coord = (hit[2].rsplit('_', 3))[1:]

		# remove strand identifier from IS element candidate
		# coord: '_1734599_1736514_', '_3720680_3722049_'
		#coord = coord[:-1]
		coord = '_'.join(coord[:-1])

		if coord not in coord_key:
			hits_refined.append(hit)
			coord_key.append(coord)

	return hits_refined


# Filter hits by the specified E-value cutoff
# mtblout_hits_sorted: a sorted hits list
def refine_hmm_hits_evalue(tblout_hits_sorted, e_value):
	# e_value_type: 0 for best_domain_value, 4 for full_sequence_value
	e_value_type = SORT_BY

	# Option1:
	#	1) Keeping hits with either best_domain_value or full_sequence_value <= e_value
	if not (tblout_hits_sorted[-1][e_value_type] > e_value):
	#
	# Option2:
	#	1) Keeping hits with both best_domain_value and full_sequence_value <= e_value
	# stringent cutoff: hit must be significant with best_domain_value and full_sequence_value
	#if not (tblout_hits_sorted[-1][0] > e_value) and not (tblout_hits_sorted[-1][4] > e_value):
	#
		return tblout_hits_sorted

	for i, hit in enumerate(tblout_hits_sorted):
		# Option1:
		#	1) Keeping hits with either best_domain_value or full_sequence_value <= e_value
		if hit[e_value_type] > e_value:
		#
		# Option2:
		#	1) Keeping hits with both best_domain_value and full_sequence_value <= e_value
		# stringent cutoff: hit must be significant with best_domain_value and full_sequence_value
		#if hit[0] > e_value or hit[4] > e_value:
		#
			return tblout_hits_sorted[:i]


# remove redundant IS elements with same boundary and same TIR
# The redundant IS elements may be produced by two neighboring ORFs extending to the same TIR boundary.
# For example, ('NC_000913.3', 4518418, 4519014, '+') and ('NC_000913.3', 4519015, 4519224, '+') will 
# be extended to the same TIR boundary:
# (45, 22, 25, 0, 4518470, 4518494, 4519217, 4519241, 'TCGGTAATGCTGCCAACTTACTGAT', 'TCGGTAATGACTCCAACTTACTGAT').
# mhits: {seqid: hits, ..., seqid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'bd': bd}
# orf: (seqid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# bd: [start, end], boundary of hit (IS element)
# 
def removeRedundantIS(mhits):
	# hmmhit: (familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
	if SORT_BY == 4:
		sortby = 2
	else:
		sortby = 1

	mhitsNew = {}
	for accid, hits in mhits.items():
		hitsNew = []
		sortedHits = sorted(hits, key=lambda x: x['bd'])
		for k, g in itertools.groupby(sortedHits, key=lambda x: x['bd']):
			redundantHits = list(g)
			if len(redundantHits) > 1:
				redundantHits.sort(key = lambda x: x['hmmhit'][sortby])
				print('Remove redundant IS elements and keep only one with the least evalue:')
				for hit in redundantHits:
					print('redundant hit', hit['bd'], hit['occurence']['ncopy4is'], 
							hit['orf'], hit['hmmhit'])
			hitsNew.append(redundantHits[0])
		mhitsNew[accid] = hitsNew
	return mhitsNew


def clusterIntersect(hits, ids):
	# remove the intersected hits
	hitsNew = [hit for i, hit in enumerate(hits) if i not in ids]

	idsList = sorted(ids)
	# create the reduced submatrix of nhits original observations in 2-dimenstional space, 
	# len(ids) * 2 matrix, where only intersected hits are retained and each row is a hit with
	# two features (genome coordinates of a hit).
	# 
	data = []
	for id in idsList:
		data.append(hits[id]['bd'])

	Y = numpy.array(data, int)
	print('data: {}\n{}'.format(Y.shape, Y))

	distMatrix = scipy.spatial.distance.pdist(Y, tools.distFunction)
	#distMatrix = scipy.spatial.distance.pdist(Y, metric='euclidean')
	#print('distMatrix: {}\n{}'.format(distMatrix.shape, distMatrix))

	# fastcluster requires the dissimilarity matrix instead of similarity matrix!
	hclusters = fastcluster.linkage(distMatrix, method='single', preserve_input='False')
	del distMatrix
	#cophenet = scipy.cluster.hierarchy.cophenet(hclusters, distMatrix)
	#print('cophenetCorrelation = {}'.format(cophenet[0]))
	#nids = len(ids)
	#print('nids={} timesOfMergingCluster={}'.format(nids, len(hclusters)))
	#for i, cluster in enumerate(hclusters):
	#	print('cluster {:>3} {:>6} {:>6} {:>9.2g} {:>6}'.format(i, int(cluster[0]), int(cluster[1]), cluster[2], int(cluster[3])))
	for i, id in enumerate(idsList):
		print('intersected hits', i, hits[id]['bd'], hits[id]['orf'], hits[id]['occurence'], hits[id]['hmmhit'], hits[id]['tirs'])

	# dengrogram of hierachical clustering
	#scipy.cluster.hierarchy.dendrogram(hclusters)

	# form flat clusters from the hierarchical clustering
	# Note: t=1.1 instead of 1.0 ensures that the intersected hits with only 1 bp intersect are included in same cluster. 
	t = 1.1
	clusters = scipy.cluster.hierarchy.fcluster(hclusters, t, criterion='distance')

	# determine the representative hit in each cluster
	# rules: 
	#	1) multiple-copy hit has priority over single-copy hit
	#	2) and then the hit with lower e-value has priority over hit with higher e-value
	clustersDic = {}
	for i, clusterid in enumerate(clusters):
		if clusterid in clustersDic.keys():
			clustersDic[clusterid].append(i)
		else:
			clustersDic[clusterid] = [i]
	print(clustersDic)

	# determine the representative hit for each cluster and append the representative hits to hitsNew
	for cluster in clustersDic.values():
		# sort and group hits into two groups, multiple-copy and single-copy, where multiple-copy hits with 
		# different copy number are grouped into same group, multiple-copy group.
		cluster.sort(key = lambda x: 2 if hits[idsList[x]]['occurence']['ncopy4is']>1 else 1, reverse=True)
		gs = itertools.groupby(cluster, key = lambda x: 2 if hits[idsList[x]]['occurence']['ncopy4is']>1 else 1)

		# len(gs) == 2 if both multiple- and single-copy groups are available in cluster, 
		# len(gs) == 1 if either multiple-copy only or single-copy only group is available in cluster.
		# sort hits by e-value where gs[0] is groups containing hits with the most of copy number.
		k_g = next(gs) # get the first tuple from gs, (k,g)
		g = list(k_g[1])
		g.sort(key = lambda x: hits[idsList[x]]['hmmhit'][1])
		# id of the representative hit with the least e-value, where hit == hits[idsList[id]]
		repid = g[0]
		hit = hits[idsList[repid]]
		hitsNew.append(hit)
		print('representative hit: repid={} hitid={} hitbd={} cluster={}'.format(
			repid, idsList[repid], hit['bd'], cluster))
	hitsNew.sort(key = lambda x: x['bd'][0])
	return hitsNew

def removeOverlappedHits(mhits):
	mhitsNew = {}
	for accid, hits in mhits.items():
		ids = set()
		for pair in itertools.combinations(range(len(hits)), 2):
			#if hits[pair[0]]['orf'][3] != hits[pair[1]]['orf'][3]:
			#	continue # count hits with orf on different strands as different IS

			bd1 = hits[pair[0]]['bd']
			bd2 = hits[pair[1]]['bd']
			measure, threshold = tools.chooseMeasure(bd1, bd2)
			if measure < threshold:
				continue

			ids.update(pair)
		if len(ids) > 0:
			print('{}: {} intersected hits found, clustering them to pick the representative for each cluster'.format(accid, len(ids)))
			hitsNew = clusterIntersect(hits, ids)
		else:
			hitsNew = hits[:]

		mhitsNew[accid] = hitsNew
	return mhitsNew

	
# Write to files the predictions for each genome sequence
# 
# mhits: {accid: hits, ..., accid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'occurence': occurence, 'isScore': isScore}
# orf: (accid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (clusterName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# occurence: {'ncopy4orf': ncopy4orf, 'sim4orf': sim4orf, 'ncopy4is': ncopy4is, 'sim4is': sim4is}
# 	ncopy4orf: copy number of the specific Tpase ORF with sim > constants.sim4iso in same DNA sequence
# 	ncopy4is: copy number of the specific IS element with sim > constants.sim4iso in same DNA sequence
# 	sim4orf: Tpase ORF with identicalBases/lengthOfAlignment > sim are regarded as the same Tpase
# 	sim4is: IS elements with identicalBases/lengthOfAlignment > sim are regarded as the same IS element
# isScore: {'evalue': score4evalue, 'tir': score4tir, 'dr': score4dr, 'occurence': score4occurence, 
#		'score': isScore, 'ncopy4orf': ncopy4orf, 'ncopy4is': ncopy4is, 'irSim': irSim}
#
def outputIndividual(mhits, mDNA, proteomes, morfsMerged):
	#fmtStrPrediction = '{:<30} # NCBI sequence ID
	#		{:<11} # family
	#		{:<59} # subgroup (cluster) ID
	#		{:>12} {:>12} {:>6} # boundary and length of IS element
	#		{:>8} # copy number of IS element
	#		{:>12} {:>12} {:>12} {:>12} # boundary of tir: start1, end1, start2, end2
	#		{:>5} {:>4} {:>5} {:>5} # characteristics of tir: score, irId, irLen, nGaps 
	#		{:>12} {:>12} {:>6} {:>7} # orf: orfBegin, orfEnd, strand, length
	#		{:>9.2g} {:>2}  # hmmhit
	#
	#		'seqID', # NCBI sequence ID
	#		'family', # family name 
	#		'cluster', # subgroup, cluster ID created by CD-hit clustering
	#		'isBegin', 'isEnd', 'len4is', # boundary and length of IS element
	#		'ncopy4is', # copy number of IS element
	#		'start1', 'end1', 'start2', 'end2', # boundary of tir
	#		'score', 'irId', 'irLen', 'nGaps', # characteristics of tir: 
	#		'orfBegin', 'orfEnd', 'strand', 'len4orf', # tpase ORF: orfBegin, orfEnd, strand, length
	#		'E-value', 'ov', # hmmhit: evalue4best1domain, overlap number output by hmmer
	#		
	#
	fmtStrTitlePredictionNoSeq = '{:<30} {:<11} {:<59} {:>12} {:>12} {:>6} {:>8} {:>12} {:>12} {:>12} {:>12} {:>5} {:>4} {:>5} {:>5} {:>12} {:>12} {:>6} {:>7} {:>9} {:>2}'
	fmtStrPredictionNoSeq = '{:<30} {:<11} {:<59} {:>12} {:>12} {:>6} {:>8} {:>12} {:>12} {:>12} {:>12} {:>5} {:>4} {:>5} {:>5} {:>12} {:>12} {:>6} {:>7} {:>9.2g} {:>2}'

	#print(fmtStrTitlePrediction.format(
	# sort keys of dictionary
	for seqid in sorted(mhits.keys()):
		hits = mhits[seqid]
		if len(hits) == 0:
			continue
		org, fileid, seq = mDNA[seqid]

		# proteomes: {seqid: (filename, genes), ..., seqid: (filename, genes)}
		#	genes: {orfseqid: faa, ..., orfseqid: faa}
		#	orfseqid: 'seqid_orfid', orfid = 'begin_end_strand'
		if seqid not in proteomes.keys():
			continue
		proteins = proteomes[seqid][1]

		if seqid in morfsMerged.keys():
			orfsMerged = morfsMerged[seqid]
		else:
			orfsMerged = set()


		dir4output = os.path.join(constants.dir4prediction, org)
		tools.makedir(dir4output)
		outFile = os.path.join(dir4output, '.'.join([fileid, 'out']))
		sumFile = os.path.join(dir4output, '.'.join([fileid, 'sum']))
		gffFile =  os.path.join(dir4output, '.'.join([fileid, 'gff']))
		fp = open(outFile, 'w')
		fp4sum = open(sumFile, 'w')
		fp4gff = open(gffFile, 'w')
		outFile4isfna = os.path.join(dir4output, '.'.join([fileid, 'is', 'fna']))
		outFile4orffna = os.path.join(dir4output, '.'.join([fileid, 'orf', 'fna']))
		outFile4orffaa = os.path.join(dir4output, '.'.join([fileid, 'orf', 'faa']))
		fp4isfna = open(outFile4isfna, 'w')
		fp4orffna = open(outFile4orffna, 'w')
		fp4orffaa = open(outFile4orffaa, 'w')

		# sort by isBegin if tirs exist, else by orfBegin
		#hits.sort(key = lambda x: x['tirs'][0][-6] if len(x['tirs'])>0 and len(x['tirs'][0])>0 else x['orf'][1])
		# sort by isBegin
		hits.sort(key = lambda x: x['bd'][0])
		# familySumBySeq: {'family1': nis4family1, ..., 'familyn': nis4familyn}
		# bpsBySeq: {'family1': bps, ..., 'familyn': bps}
		familySumBySeq = {}
		bpsBySeq = {}

		print('##gff-version 3', file = fp4gff)

		print(fmtStrTitlePredictionNoSeq.format(
			'seqID', # NCBI sequence ID
			'family', # family name from ISfinder
			'cluster', # cluster ID created by CD-hit clustering
			'isBegin', 'isEnd', 'len4is', # boundary and length of IS element
			'ncopy4is', # copy number of IS element
			'start1', 'end1', 'start2', 'end2', # boundary of tir
			'score', 'irId', 'irLen', 'nGaps', # characteristics of tir: 
			'orfBegin', 'orfEnd', 'strand', 'len4orf', # tpase ORF: orfBegin, orfEnd, strand, length
			'E-value', 'ov', # hmmhit: best1domain e-value and overlap number output by hmmer
			), 
			file = fp)
		print('#', '-' * 139, file = fp)

		IDnum = 0 
		#for hit in hits:
		for hitID, hit in enumerate(hits):
			orfBegin, orfEnd, strand = hit['orf'][1:]
			len4orf = orfEnd - orfBegin + 1
			cluster, best1domE, fullSeqE, ov, = hit['hmmhit']
			if 'IS200_IS605_' in cluster:
				family = 'IS200/IS605'
			else:
				family = cluster.split('_',1)[0]
			occurence = hit['occurence']
			ncopy4is, sim4is, ncopy4orf, sim4orf = occurence['ncopy4is'], occurence['sim4is'], occurence['ncopy4orf'], occurence['sim4orf']
			if len(hit['tirs']) > 0:
				tirs = hit['tirs']
				score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2 = tirs[0]
				#isBegin, isEnd = start1, end2
			else:
				score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2 = (0, 0, 0, 0, 0, 0, 0, 0, '-', '-')
				#isBegin, isEnd = orfBegin, orfEnd
			isBegin, isEnd = hit['bd']
			len4is = isEnd - isBegin + 1

			# output .gff file
			# gff3 format specifications, refer to 
			# https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
			#
			IDnum += 1
			ID = str(IDnum)
			# IS element
			print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(
				seqid, # NCBI sequence ID
				'ISEScan',
				'insertion_sequence',
				isBegin, isEnd,
				'.',
				#'.', # IS element is DNA transposon and not stranded.
				strand, # IS element is DNA transposon and not stranded but usually labeled by strand of Tpase main ORF.
				'.',
				';'.join(['ID=is'+ID, 'family='+family, 'cluster='+str(cluster)])
				), file = fp4gff)
			# with TIR
			if irLen > 0:
				# the first part of TIR
				print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(
					seqid, # NCBI sequence ID
					'ISEScan',
					'terminal_inverted_repeat',
					start1, end1, 
					'.',
					#'.', # IS element is DNA transposon and not stranded.
					strand, # IS element is DNA transposon and not stranded but usually labeled by strand of Tpase main ORF.
					'.',
					';'.join(['ID=tir'+ID, 'parent=is'+ID])
					), file = fp4gff)
				# the second part of TIR
				print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(
					seqid, # NCBI sequence ID
					'ISEScan',
					'terminal_inverted_repeat',
					start2, end2, 
					'.',
					#'.', # IS element is DNA transposon and not stranded.
					strand, # IS element is DNA transposon and not stranded but usually labeled by strand of Tpase main ORF.
					'.',
					';'.join(['ID=tir'+ID, 'parent=is'+ID])
					), file = fp4gff)

			# output .out file
			#print(fmtStrPrediction.format(
			print(fmtStrPredictionNoSeq.format(
				seqid, # NCBI sequence ID
				family, # family name
				cluster, # cluster id
				isBegin, isEnd, len4is, # boundary and length of IS element
				ncopy4is, # copy number of IS element
				start1, end1, start2, end2, # tir boundary
				score, irId, irLen, nGaps, # characteristics of tir 
				orfBegin, orfEnd, strand, len4orf, # orf, probably virtual ORF
				best1domE, ov, # hmmhit
				),
				file = fp)

			# summarize
			if family in familySumBySeq.keys():
				familySumBySeq[family] += 1
				bpsBySeq[family] += len4is
			else:
				familySumBySeq[family] = 1
				bpsBySeq[family] = len4is
			
			# output sequence of IS element
			if strand == '-':
				fna4is = tools.complementDNA(seq[isBegin-1: isEnd], '1')[::-1]
			else:
				fna4is = seq[isBegin-1: isEnd]
			head4fna4is = '_'.join([hit['orf'][0], str(isBegin), str(isEnd), strand])
			des = cluster
			head4fna4is = ' '.join([head4fna4is, des])
			fasta4fna4is = tools.fasta_format(head4fna4is, fna4is)
			fp4isfna.write(fasta4fna4is)

			# ORF
			orfStr = '_'.join([str(x) for x in hit['orf'][1:]])
			head4fna4orf = '_'.join([hit['orf'][0], orfStr])

			orfs4merged = []
			for orf in orfsMerged:
				# The merged orfs must be located at the same strand.
				#if  hit['orf'][1] <= orf[1] and hit['orf'][2] >= orf[2] and hit['orf'][3] == orf[3]:
				# The merged orfs may be located at the different strands.
				if  hit['orf'][1] <= orf[1] and hit['orf'][2] >= orf[2]:
					orfs4merged.append(orf)
					# A hit is created by two merged ORFs.
					# At most two ORF hits (ORFs )can be merged into a larger virtual ORF, 
					# namely, a larger ORF hit. The other ORFs are thrown if there are 
					# more than two ORFs merged in the current large virtual ORF.
					#if len(orfs4merged) == 2:
					#	break
			if len(orfs4merged) > 0:
				# sort by start coordinate of ORF
				orfs4merged.sort(key = operator.itemgetter(1))
				for orf1 in orfs4merged:
					orf1str = '_'.join(str(x) for x in orf1[1:])
					# amino acid sequence
					head4faa4orf1 = '_'.join([orf1[0], orf1str])
					faa4orf1 = proteins[head4faa4orf1]
					fasta4faa4orf1 = tools.fasta_format('{} {} merged in virtual ORF {}'.format(
						head4faa4orf1, orf1str, orfStr), faa4orf1)
					fp4orffaa.write(fasta4faa4orf1)

					# nucleic acid sequence
					head4fna4orf1 = '_'.join([orf1[0], orf1str])
					if orf1[3] == '-':
						fna4orf1 = tools.complementDNA(seq[orf1[1]-1: orf1[2]], '1')[::-1]
					else:
						fna4orf1 = seq[orf1[1]-1: orf1[2]]
					fasta4fna4orf1 = tools.fasta_format('{} {} merged in virtual ORF {}'.format(
						head4fna4orf1, orf1str, orfStr), fna4orf1)
					fp4orffna.write(fasta4fna4orf1)
			else:
				# amino acid sequence
				faa4orf = proteins[head4fna4orf]
				fasta4faa4orf = tools.fasta_format(head4fna4orf, faa4orf)
				fp4orffaa.write(fasta4faa4orf)

				# nucleic acid sequence
				if strand == '-':
					fna4orf = tools.complementDNA(seq[orfBegin-1: orfEnd], '1')[::-1]
				else:
					fna4orf = seq[orfBegin-1: orfEnd]
				fasta4fna4orf = tools.fasta_format(head4fna4orf, fna4orf)
				fp4orffna.write(fasta4fna4orf)

		fp4isfna.close()
		fp4orffna.close()
		fp4orffaa.close()
		fp4gff.close()
		fp.close()

		print('{:<11} {:>6} {:>7} {:>15}'.format('family', 'nIS', '%Genome', 'bps4IS'), file=fp4sum)
		#print('-' * 18, file=fp4sum)
		nis4seq = 0
		bps4seq = 0
		len4DNA = len(seq)
		for family in sorted(familySumBySeq.keys()):
			nis = familySumBySeq[family]
			bps4family = bpsBySeq[family]
			print('{:<11} {:>6} {:>7.2g} {:>15}'.format(family, nis, 
				(bps4family/len4DNA)*100, bps4family), file=fp4sum)
			nis4seq += nis
			bps4seq += bps4family

		print('{:<11} {:>6} {:>7.2g} {:>15} {:>15}'.format('total', nis4seq, 
			(bps4seq/len4DNA)*100, bps4seq, len4DNA), file=fp4sum)
		fp4sum.close()
		if nis4seq == 0:
			print('No valid IS element was found for', seqid)


# Write to files the predictions for each genome sequence
# 
# mhits: {accid: hits, ..., accid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'occurence': occurence, 'isScore': isScore}
# orf: (accid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (clusterName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# occurence: {'ncopy4orf': ncopy4orf, 'sim4orf': sim4orf, 'ncopy4is': ncopy4is, 'sim4is': sim4is}
# 	ncopy4orf: copy number of the specific Tpase ORF with sim > constants.sim4iso in same DNA sequence
# 	ncopy4is: copy number of the specific IS element with sim > constants.sim4iso in same DNA sequence
# 	sim4orf: Tpase ORF with identicalBases/lengthOfAlignment > sim are regarded as the same Tpase
# 	sim4is: IS elements with identicalBases/lengthOfAlignment > sim are regarded as the same IS element
# isScore: {'evalue': score4evalue, 'tir': score4tir, 'dr': score4dr, 'occurence': score4occurence, 
#		'score': isScore, 'ncopy4orf': ncopy4orf, 'ncopy4is': ncopy4is, 'irSim': irSim}
#
# orgfileid: org/fileid, character string, e.g. HMASM/SRS078176.scaffolds.fa
def outputIS4multipleSeqOneFile(mhits, mDNA, proteomes, morfsMerged, orgfileid):
	#fmtStrPrediction = '{:<60} # NCBI sequence ID
	#		{:<11} # family
	#		{:<59} # subgroup (cluster) ID
	#		{:>12} {:>12} {:>6} # boundary and length of IS element
	#		{:>8} # copy number of IS element
	#		{:>12} {:>12} {:>12} {:>12} # boundary of tir: start1, end1, start2, end2
	#		{:>5} {:>4} {:>5} {:>5} # characteristics of tir: score, irId, irLen, nGaps 
	#		{:>12} {:>12} {:>6} {:>7} # orf: orfBegin, orfEnd, strand, length
	#		{:>9.2g} {:>2}  # hmmhit
	#
	#		'seqID', # NCBI sequence ID
	#		'family', # family name 
	#		'cluster', # subgroup, cluster ID created by CD-hit clustering
	#		'isBegin', 'isEnd', 'len4is', # boundary and length of IS element
	#		'ncopy4is', # copy number of IS element
	#		'start1', 'end1', 'start2', 'end2', # boundary of tir
	#		'score', 'irId', 'irLen', 'nGaps', # characteristics of tir: 
	#		'orfBegin', 'orfEnd', 'strand', 'len4orf', # tpase ORF: orfBegin, orfEnd, strand, length
	#		'E-value', 'ov', # hmmhit: evalue4best1domain, overlap number output by hmmer
	#		
	#
	fmtStrTitlePredictionNoSeq = '{:<60} {:<11} {:<59} {:>12} {:>12} {:>6} {:>8} {:>12} {:>12} {:>12} {:>12} {:>5} {:>4} {:>5} {:>5} {:>12} {:>12} {:>6} {:>7} {:>9} {:>2}'
	fmtStrPredictionNoSeq = '{:<60} {:<11} {:<59} {:>12} {:>12} {:>6} {:>8} {:>12} {:>12} {:>12} {:>12} {:>5} {:>4} {:>5} {:>5} {:>12} {:>12} {:>6} {:>7} {:>9.2g} {:>2}'

	fmtStrTitleSum = '{:<60} {:<11} {:>6} {:>7} {:>15} {:>15}'
	fmtStrSum = '{:<60} {:<11} {:>6} {:>7.2f} {:>15} {:>15}'

	common4output = os.path.join(constants.dir4prediction, orgfileid)
	outFile = '.'.join([common4output, 'out'])
	sumFile = '.'.join([common4output, 'sum'])
	gffFile =  '.'.join([common4output, 'gff'])

	tools.makedir(os.path.dirname(outFile))

	fp = open(outFile, 'w')
	print(fmtStrTitlePredictionNoSeq.format(
		'seqID', # sequence ID
		'family', # family name from ISfinder
		'cluster', # cluster ID created by CD-hit clustering
		'isBegin', 'isEnd', 'len4is', # boundary and length of IS element
		'ncopy4is', # copy number of IS element
		'start1', 'end1', 'start2', 'end2', # boundary of tir
		'score', 'irId', 'irLen', 'nGaps', # characteristics of tir: 
		'orfBegin', 'orfEnd', 'strand', 'len4orf', # tpase ORF: orfBegin, orfEnd, strand, length
		'E-value', 'ov', # hmmhit: best1domain e-value and overlap number output by hmmer
		), 
		file = fp)
	print('#', '-' * 139, file = fp)

	fp4sum = open(sumFile, 'w')
	print(fmtStrTitleSum.format(
		'# seqid', 'family', 'nIS', '%Genome', 'bps4IS', 'dnaLen'), file=fp4sum)
	nis4seqTotal = 0
	bps4seqTotal = 0
	len4DNATotal = 0

	fp4gff = open(gffFile, 'w')
	print('##gff-version 3', file = fp4gff)

	outFile4isfna = '.'.join([common4output, 'is', 'fna'])
	outFile4orffna = '.'.join([common4output, 'orf', 'fna'])
	outFile4orffaa = '.'.join([common4output, 'orf', 'faa'])
	fp4isfna = open(outFile4isfna, 'w')
	fp4orffna = open(outFile4orffna, 'w')
	fp4orffaa = open(outFile4orffaa, 'w')


	#print(fmtStrTitlePrediction.format(
	# sort keys of dictionary
	for seqid in sorted(mhits.keys()):
		hits = mhits[seqid]
		if len(hits) == 0:
			continue

		org, fileid, seq = mDNA[seqid]

		# proteomes: {seqid: (filename, genes), ..., seqid: (filename, genes)}
		#	genes: {orfseqid: faa, ..., orfseqid: faa}
		#	orfseqid: 'seqid_orfid', orfid = 'begin_end_strand'

		if seqid not in proteomes.keys():
			continue
		proteins = proteomes[seqid][1]

		if seqid in morfsMerged.keys():
			orfsMerged = morfsMerged[seqid]
		else:
			orfsMerged = set()

		# sort by isBegin if tirs exist, else by orfBegin
		#hits.sort(key = lambda x: x['tirs'][0][-6] if len(x['tirs'])>0 and len(x['tirs'][0])>0 else x['orf'][1])
		# sort by isBegin
		hits.sort(key = lambda x: x['bd'][0])
		# familySumBySeq: {'family1': nis4family1, ..., 'familyn': nis4familyn}
		# bpsBySeq: {'family1': bps, ..., 'familyn': bps}
		familySumBySeq = {}
		bpsBySeq = {}


		IDnum = 0 
		#for hit in hits:
		for hitID, hit in enumerate(hits):
			orfBegin, orfEnd, strand = hit['orf'][1:]
			len4orf = orfEnd - orfBegin + 1
			cluster, best1domE, fullSeqE, ov, = hit['hmmhit']
			if 'IS200_IS605_' in cluster:
				family = 'IS200/IS605'
			else:
				family = cluster.split('_',1)[0]
			occurence = hit['occurence']
			ncopy4is, sim4is, ncopy4orf, sim4orf = occurence['ncopy4is'], occurence['sim4is'], occurence['ncopy4orf'], occurence['sim4orf']
			if len(hit['tirs']) > 0:
				tirs = hit['tirs']
				score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2 = tirs[0]
				#isBegin, isEnd = start1, end2
			else:
				score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2 = (0, 0, 0, 0, 0, 0, 0, 0, '-', '-')
				#isBegin, isEnd = orfBegin, orfEnd
			isBegin, isEnd = hit['bd']
			len4is = isEnd - isBegin + 1

			# output .gff file
			# gff3 format specifications, refer to 
			# https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
			#
			IDnum += 1
			ID = str(IDnum)
			# IS element
			isid = '_'.join([seqid, 'IS', ID])
			print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(
				seqid, # sequence ID
				'ISEScan',
				'insertion_sequence',
				isBegin, isEnd,
				'.',
				#'.', # IS element is DNA transposon and not stranded.
				strand, # IS element is DNA transposon and not stranded but usually labeled by strand of Tpase main ORF.
				'.',
				';'.join(['ID='+isid, 'family='+family, 'cluster='+str(cluster)])
				), file = fp4gff)
			# with TIR
			tirid = '_'.join([isid,'TIR'])
			parentid = isid
			if irLen > 0:
				# the first part of TIR
				print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(
					seqid, # NCBI sequence ID
					'ISEScan',
					'terminal_inverted_repeat',
					start1, end1, 
					'.',
					#'.', # IS element is DNA transposon and not stranded.
					strand, # IS element is DNA transposon and not stranded but usually labeled by strand of Tpase main ORF.
					'.',
					';'.join(['ID='+tirid, 'parent='+isid])
					), file = fp4gff)
				# the second part of TIR
				print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(
					seqid, # NCBI sequence ID
					'ISEScan',
					'terminal_inverted_repeat',
					start2, end2, 
					'.',
					#'.', # IS element is DNA transposon and not stranded.
					strand, # IS element is DNA transposon and not stranded but usually labeled by strand of Tpase main ORF.
					'.',
					';'.join(['ID='+tirid, 'parent='+isid])
					), file = fp4gff)

			# output .out file
			#print(fmtStrPrediction.format(
			print(fmtStrPredictionNoSeq.format(
				seqid, # NCBI sequence ID
				family, # family name
				cluster, # cluster id
				isBegin, isEnd, len4is, # boundary and length of IS element
				ncopy4is, # copy number of IS element
				start1, end1, start2, end2, # tir boundary
				score, irId, irLen, nGaps, # characteristics of tir 
				orfBegin, orfEnd, strand, len4orf, # orf, probably virtual ORF
				best1domE, ov, # hmmhit
				),
				file = fp)

			# summarize
			if family in familySumBySeq.keys():
				familySumBySeq[family] += 1
				bpsBySeq[family] += len4is
			else:
				familySumBySeq[family] = 1
				bpsBySeq[family] = len4is
			
			# output sequence of IS element
			if strand == '-':
				fna4is = tools.complementDNA(seq[isBegin-1: isEnd], '1')[::-1]
			else:
				fna4is = seq[isBegin-1: isEnd]
			head4fna4is = '_'.join([hit['orf'][0], str(isBegin), str(isEnd), strand])
			des = cluster
			head4fna4is = ' '.join([head4fna4is, des])
			fasta4fna4is = tools.fasta_format(head4fna4is, fna4is)
			fp4isfna.write(fasta4fna4is)

			# ORF
			orfStr = '_'.join([str(x) for x in hit['orf'][1:]])
			head4fna4orf = '_'.join([hit['orf'][0], orfStr])

			orfs4merged = []
			for orf in orfsMerged:
				# The merged orfs must be located at the same strand.
				#if  hit['orf'][1] <= orf[1] and hit['orf'][2] >= orf[2] and hit['orf'][3] == orf[3]:
				# The merged orfs may be located at the different strands.
				if  hit['orf'][1] <= orf[1] and hit['orf'][2] >= orf[2]:
					orfs4merged.append(orf)
					# A hit is created by two merged ORFs.
					# At most two ORF hits (ORFs )can be merged into a larger virtual ORF, 
					# namely, a larger ORF hit. The other ORFs are thrown if there are 
					# more than two ORFs merged in the current large virtual ORF.
					#if len(orfs4merged) == 2:
					#	break
			if len(orfs4merged) > 0:
				# sort by start coordinate of ORF
				orfs4merged.sort(key = operator.itemgetter(1))
				for orf1 in orfs4merged:
					orf1str = '_'.join(str(x) for x in orf1[1:])
					# amino acid sequence
					head4faa4orf1 = '_'.join([orf1[0], orf1str])
					faa4orf1 = proteins[head4faa4orf1]
					fasta4faa4orf1 = tools.fasta_format('{} {} merged in virtual ORF {}'.format(
						head4faa4orf1, orf1str, orfStr), faa4orf1)
					fp4orffaa.write(fasta4faa4orf1)

					# nucleic acid sequence
					head4fna4orf1 = '_'.join([orf1[0], orf1str])
					if orf1[3] == '-':
						fna4orf1 = tools.complementDNA(seq[orf1[1]-1: orf1[2]], '1')[::-1]
					else:
						fna4orf1 = seq[orf1[1]-1: orf1[2]]
					fasta4fna4orf1 = tools.fasta_format('{} {} merged in virtual ORF {}'.format(
						head4fna4orf1, orf1str, orfStr), fna4orf1)
					fp4orffna.write(fasta4fna4orf1)
			else:
				# amino acid sequence
				faa4orf = proteins[head4fna4orf]
				fasta4faa4orf = tools.fasta_format(head4fna4orf, faa4orf)
				fp4orffaa.write(fasta4faa4orf)

				# nucleic acid sequence
				if strand == '-':
					fna4orf = tools.complementDNA(seq[orfBegin-1: orfEnd], '1')[::-1]
				else:
					fna4orf = seq[orfBegin-1: orfEnd]
				fasta4fna4orf = tools.fasta_format(head4fna4orf, fna4orf)
				fp4orffna.write(fasta4fna4orf)

		#print('>'+seqid, file=fp4sum)
		#print('-' * 18, file=fp4sum)
		nis4seq = 0
		bps4seq = 0
		len4DNA = len(seq)
		for family in sorted(familySumBySeq.keys()):
			nis = familySumBySeq[family]
			bps4family = bpsBySeq[family]
			print(fmtStrSum.format(
				seqid, family, nis, 
				(bps4family/len4DNA)*100, bps4family, len4DNA), file=fp4sum)
			nis4seq += nis
			bps4seq += bps4family
		nis4seqTotal += nis4seq
		bps4seqTotal += bps4seq

	# The sequences without IS also need to be counted in len4DNATotal.
	len4DNATotal = sum([len(v[2]) for v in mDNA.values()])
	
	#fileid = os.path.basename(sumFile).rsplit('.',1)[0]
	print(fmtStrSum.format(
		fileid, 'total', 
		nis4seqTotal, (bps4seqTotal/len4DNATotal)*100, bps4seqTotal, len4DNATotal), file=fp4sum)
	if nis4seq == 0:
		print('No valid IS element was found for', fileid)
		
	fp4isfna.close()
	fp4orffna.close()
	fp4orffaa.close()
	fp4gff.close()
	fp.close()
	fp4sum.close()


# mtblout_hits:		[(accid, hits_sorted_refined), ..., (accid, hits_sorted_refined)]
# hits_sorted_refined:	[hit, ..., hit]
# hit:			(best_1_domain_E-value, hit_line, compound_ID, query_name, full_sequence_E-value, overlap_number)
# best_1_domain_E-value:float, best 1 domain E-value
# hit_line:		string, hit line
# compound_ID:		string, compound ID, for example, gi|15644634|ref|NC_000915.1|_923867_924196_+
# query_name:		string, name of query sequence or profile, for example, IS1.long.pep.all
# full_sequence_E-value:float, full sequence E-value
# overlap_number:	int, overlap number, how many of envelopes overlap other envelopes; pay special attention to hit with ov > 0
#
# morfHits: {accid: orfHits, ..., accid: orfHits}
# orfHits: [orfhit, ..., orfhit]
# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
def convertHits2orfHits(mtblout_hits):
	morfHits = {}
	for item in mtblout_hits:
		accid, hits = item
		if len(hits) == 0:
			continue
		orfHits = []
		for hit in hits:
			orfHits.append(convertHit2orfHit(hit))
		morfHits[accid] = orfHits
	return morfHits

# Return (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# orf: (accid, begin, end, strand)
#
# hit: (best_1_domain_E-value, hit_line, compound_ID, query_name, full_sequence_E-value, overlap_number)
#
def convertHit2orfHit(hit):
	best1domainEvalue = hit[0]
	compoundID, queryName, fullSequenceEvalue, overlapNumber = hit[2:]
	# compoundID: 'gi|256374160|ref|NC_013093.1|_6781872_6782144_-'
	# queryName: 'IS1_0.faa', 'IS110_3|IS110||ISKOL6|'
	orfStr = compoundID.rsplit('_', 3)
	#orf = (orfStr[0].rstrip('|').rsplit('|',1)[-1], int(orfStr[-3]), int(orfStr[-2]), orfStr[-1])
	orf = (orfStr[0], int(orfStr[-3]), int(orfStr[-2]), orfStr[-1])
	familyName = queryName.split('.', 1)[0]
	return (orf, familyName, best1domainEvalue, fullSequenceEvalue, overlapNumber)


# Merge the neighboring significant ORFs with distance <= maxDistBetweenOrfs, return mOrfHits
# morfHits: {accid: orfHits, ..., accid: orfHits}
# orfHits: [orfhit, ..., orfhit]
# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# orf: (accid, begin, end, strand)
def mergeOrfs(mOrfHits, maxDistBetweenOrfs):
	morfHitsCopy = {}
	morfsMerged = {}
	for accid in mOrfHits:
		if len(mOrfHits[accid]) == 0:
			continue

		# combinations of hits while two hits locate on the same strand
		#hitPairs = list(itertools.filterfalse(lambda x: x[0][0][3] != x[1][0][3], 
		#	itertools.combinations(mOrfHits[accid],2)))

		# combinations of hits while two hits locate on either the same strand or the different strands
		hitPairs = list(itertools.combinations(mOrfHits[accid],2))

		# sort hit pairs based on their gaps
		hitPairs.sort(key = lambda x: tools.intergap((x[0][0][1], x[0][0][2]), 
								(x[1][0][1], x[1][0][2]))) 

		# 1. filter out hit pairs with gap > maxDistBetweenOrfs.
		# 2. merge the orfs with gap <= maxDistBetweenOrfs, and merge only once if an orf intersected with
		#	two neighboring orfs with gap <= maxDistBetweenOrfs and another unmerged orf will be 
		#	untouched.
		orfs = []
		orfHitsMerged = []
		for x in hitPairs:
			# only merge ORFs of family IS200/IS605 as it has two ORFs(tpase gene and accessory gene)
			# and the accessory gene is usually longer than two times of the length of tpase gene.
			#if 'IS200/IS605' not in x[0][1] or 'IS200/IS605' not in x[1][1] or x[0][0][3] == x[1][0][3]:
			if 'IS200/IS605' not in x[0][1] or 'IS200/IS605' not in x[1][1]:
				continue
			orfLen1 = x[0][0][2] - x[0][0][1] + 1
			orfLen2 = x[1][0][2] - x[1][0][1] + 1
			if max(orfLen1, orfLen2) < 2 * min(orfLen1, orfLen2):
				continue

			p1 = (x[0][0][1], x[0][0][2])
			p2 = (x[1][0][1], x[1][0][2])
			if tools.intergap(p1, p2) > maxDistBetweenOrfs:
				break
			if x[0][0] in orfs:
				continue
			if x[1][0] in orfs:
				continue
			orfs.extend([x[0][0], x[1][0]])
			beginMerged, endMerged = min(p1[0], p2[0]), max(p1[1], p2[1])

			# orfhitMerged inherits the properties of the orf with smaller full_sequence_E-value
			orfMerged = (accid, beginMerged, endMerged, x[0][0][3])
			orfhitMerged = [orfMerged]
			orfhitMerged.extend(x[0][1:])
			if x[1][3] < x[0][3]:
				orfMerged = (accid, beginMerged, endMerged, x[1][0][3])
				orfhitMerged = [orfMerged]
				orfhitMerged.extend(x[1][1:])

			orfHitsMerged.append(tuple(orfhitMerged))

		# remove redundant orfs
		orfsMerged = set(orfs)
		orfHits = []
		for orfhit in mOrfHits[accid]:
			if orfhit[0] in orfsMerged:
				continue
			orfHits.append(orfhit)
		orfHits.extend(orfHitsMerged)
		orfHits.sort(key = lambda x: x[0][1])
		morfHitsCopy[accid] = orfHits
		morfsMerged[accid] = orfsMerged
	return (morfHitsCopy, morfsMerged)


# assumed: there are no orfs overlapped in genome.
# morfhitsNeighbors: {seqid: orfhitsNeighbors, ..., seqid: orfhitsNeighbors}
# orfhitsNeighbors: {orf: neighbors, ..., orf: neighbors}
# neighbors: [before, after]
# before: the orfhit before orf
# after: the orfhit after orf
# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
def hitNeighors(morfhits):
	morfhitsNeighbors = {}
	for seqid, orfhits in morfhits.items():
		n = len(orfhits)
		if n == 0:
			continue
		# start coordinates of all hits
		orfhits.sort(key = lambda x: x[0][1])
		triples = zip(orfhits, orfhits[1:], orfhits[2:])
		orfhitsNeighbors = {}
		for triple in triples:
			orf = triple[1][0]
			orfhitsNeighbors[orf] = [triple[0], triple[2]]
		if n < 2:
			orfhitsNeighbors[orfhits[0][0]] = [None, None] # only one orfhit in genome sequence
		else:
			orfhitsNeighbors[orfhits[0][0]] = [None, orfhits[1]] # first orfhit
			orfhitsNeighbors[orfhits[-1][0]] = [orfhits[-2], None] # last orfhit
		morfhitsNeighbors[seqid] = orfhitsNeighbors
		#print('hello, neighbors', orfhitsNeighbors)

	return morfhitsNeighbors

"""
steps to identify full-length IS elements in a genome DNA sequence:
> get all transposase ORFs from profile HMM search (profile HMM models of the transposases of each family/cluster against proteome)
> identify the boundary of full-length IS element:
	>> identify boundary of IS element with multiple copies by searching multiple-copy IS elements in genome sequence:
		>>> query the sequence (extended ORF) extending 500-9200 bps (based on constants.minMaxLen4is) from both ends of each ORF against genome DNA sequence database which is built from the full-length genome DNA sequence.
		>>> from the output of blast search above, retrieve the boundaries of each copy of the extended ORF, which is the IS element candidate we want.
		>>> look for TIR in the terminal sequences of the IS element candidate, where the terminal sequence runs from end of IS element candidate to the end of ORF.
		>>> use the TIR boundary to redefine the boundary of the IS element candidate if TIR is found else keep unchanged the boundary of the IS element candidate.
	>> identify boundary of single-copy IS element candidate by look for TIR directly along the outer sequences of ORF, where the outer sequence is created by extending out by 500 bps from the boundary of ORF:
		>>> look for TIR in the outer sequence
		>>> use the TIR boundary to define the boundary of full-length IS element candidate if TIR is found else the ORF is defined as full-length IS element without TIR
"""
# input: mOrfHits, mDNA
# output: mhits
#
# morfHits: {accid: orfHits, ..., accid: orfHits}
# orfHits: [orfhit, ..., orfhit]
# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# orf: (accid, begin, end, strand), example, ('NC_000915.1', 20, 303, '+')
#
# mDNA:	{accid: (org, fileid, sequence), ..., accid: (org, fileid, sequence)}
#
# mhits: {accid: hits, ..., accid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit}
# orf: (accid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
#
def writeOrfExt2file(orfExtSeqFile, orfhits, dnaseq):
	fp = open(orfExtSeqFile, 'w')
	fasta = []
	for orfhit in orfhits:
		orf, familyName = orfhit[:2]
		# familyName example: 'IS200/IS605_4|IS200/IS605|IS1341|ISCARN12|',
		# 	'IS30_0', 'IS110_25|IS110||ISLIN1|'
		if '|' in familyName:
			familyCluster = familyName.split('|',1)[0]
		else:
			familyCluster = familyName
		family, cluster = familyCluster.rsplit('_', 1)
		maxLen4is = constants.minMaxLen4is[family][1]
		#minLen4is = constants.minMaxLen4is[family][0]
		orfLen = orf[2] - orf[1] + 1
		if orfLen >= maxLen4is:
			begin, end = orf[1:3]
		else:
			begin = orf[2] - (maxLen4is - 1)
			if begin < 1:
				begin = 1
			end = orf[1] + maxLen4is - 1
			dnaLen = len(dnaseq)
			if end > dnaLen:
				end = dnaLen
		if begin >= end:
			e = 'Invalid sequence range: begin={} end={} orfBegin={} orfEnd={} maxLen4is={} family={}'.format(
					begin, end, orf[1], orf[2], maxLen4is, family)
			raise RuntimeError(e)
		seq = dnaseq[begin-1: end]
		if orf[3] == '-':
			seq = tools.complementDNA(seq, '1')[::-1]
		fastaSeq = '\n'.join(tools.chunkstring(seq, constants.fastaLineWidth))
		#headline = '>' + '_'.join([orf[0], str(begin), str(end), str(orf[1]), str(orf[2]), orf[3]])
		#headline = '>' + '_'.join([orf[0], str(minLen4is), str(begin), str(end), str(orf[1]), str(orf[2]), orf[3]])
		headline = '>' + '_'.join([orf[0], familyCluster, str(begin), str(end), str(orf[1]), str(orf[2]), orf[3]])
		fasta.extend([headline, fastaSeq])
	fp.write('\n'.join(fasta)+'\n')
	fp.close()

def writeOrfExt2fileOnStream(orfhits, dnaseq):
	fasta = []
	for orfhit in orfhits:
		orf, familyName = orfhit[:2]
		# familyName example: 'IS200/IS605_4|IS200/IS605|IS1341|ISCARN12|',
		# 	'IS30_0', 'IS110_25|IS110||ISLIN1|'
		if '|' in familyName:
			familyCluster = familyName.split('|',1)[0]
		else:
			familyCluster = familyName
		family, cluster = familyCluster.rsplit('_', 1)
		maxLen4is = constants.minMaxLen4is[family][1]
		#minLen4is = constants.minMaxLen4is[family][0]
		orfLen = orf[2] - orf[1] + 1
		if orfLen >= maxLen4is:
			begin, end = orf[1:3]
		else:
			begin = orf[2] - (maxLen4is - 1)
			if begin < 1:
				begin = 1
			end = orf[1] + maxLen4is - 1
			dnaLen = len(dnaseq)
			if end > dnaLen:
				end = dnaLen
		if begin >= end:
			e = 'Invalid sequence range: begin={} end={} orfBegin={} orfEnd={} maxLen4is={} family={}'.format(
					begin, end, orf[1], orf[2], maxLen4is, family)
			raise RuntimeError(e)
		seq = dnaseq[begin-1: end]
		if orf[3] == '-':
			seq = tools.complementDNA(seq, '1')[::-1]
		fastaSeq = '\n'.join(tools.chunkstring(seq, constants.fastaLineWidth))
		headline = '>' + '_'.join([orf[0], familyCluster, str(begin), str(end), str(orf[1]), str(orf[2]), orf[3]])
		fasta.extend([headline, fastaSeq])
	return '\n'.join(fasta)

def writeDNA2file(fp, seqid, seq):
	fastaSeq = '\n'.join(tools.chunkstring(seq, constants.fastaLineWidth))
	headline = '>' + seqid
	print(headline, fastaSeq, sep='\n', file=fp)

def writeDNA2fileOnStream(seqid, seq):
	fastaSeq = '\n'.join(tools.chunkstring(seq, constants.fastaLineWidth))
	headline = '>' + seqid
	return '\n'.join([headline, fastaSeq])

def getFullIS4seq(args):
	seqid, orfhits, dna = args
	org, fileid, seq = dna

	# replace non-standard base with 'N'
	#seq = tools.cleanDNA(seq)

	# write the extended sequences of ORFs into a file
	#orfExtSeqFile = os.path.join(constants.dir4blastout, org, fileid+'.orfext.fna')
	orfExtSeqFile = os.path.join(constants.dir4blastout, org, '.'.join([fileid,seqid,'orfext.fna']))
	tools.makedir(os.path.dirname(orfExtSeqFile))
	writeOrfExt2file(orfExtSeqFile, orfhits, seq)

	# write full-length dna sequence into a temporary file to be called by makeblastdb
	fp = tempfile.NamedTemporaryFile(mode='w', delete=False)
	writeDNA2file(fp, seqid, seq)
	fp.close()
	# make blast database
	#blastdb = os.path.join(constants.dir4blastout, org, fileid+'.fna')
	blastdb = os.path.join(constants.dir4blastout, org, '.'.join([fileid,seqid,'fna']))
	tools.seq2blastdb(fp.name, blastdb)
	os.remove(fp.name)

	# blastn(megablast) searches ORF extended sequences against genome dna sequence
	# Note: each ORF extended sequence must be longer than the corresponding IS element with 
	# 	ORF as transposase in order that the local alignment resulted from blastn can be
	#	defined as the alignment between multiple full-length IS element copies.
	#blastOut4orfExt = os.path.join(constants.dir4blastout, org, os.path.basename(blastdb)+'.out')
	blastOut4orfExt = blastdb+'.out'
	tools.blastnSearch(orfExtSeqFile, blastdb, blastOut4orfExt, strand='both', task='megablast')
	os.remove(orfExtSeqFile)
	for ext in ('.nhr', '.nin', '.nsq'):
		os.remove(blastdb+ext)

	# get copy number of ORF extended sequence
	ispairs = {}
	for k, g in itertools.groupby(
			sorted(tools.getBlastResult4dna(blastOut4orfExt), key=lambda x: x['qseqid']), 
			key=lambda x: x['qseqid']):
		ispairs[k] = list(g)
		ispairs[k].sort(key = lambda x: x['length'], reverse = True)
	os.remove(blastOut4orfExt)
	
	# orfhits: [orfhit, ..., orfhit]
	# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
	# orf: (accid, begin, end, strand), example, ('NC_000915.1', 20, 303, '+')
	for qseqid, g in ispairs.items():
		orfstr4is = '_'.join(qseqid.rsplit('_', maxsplit=3)[1:])
		for orfhit in orfhits:
			orfstr = '_'.join([str(item) for item in orfhit[0][1:]])
			if orfstr == orfstr4is:
				break
		for ispair in g:
			ispair['orfhit'] = orfhit
	return ispairs

def getFullIS4seqOnStream(args):
	seqid, orfhits, dna = args
	org, fileid, seq = dna

	# replace non-standard base with 'N'
	#seq = tools.cleanDNA(seq)

	# write the extended sequences of ORFs into a string file
	orfExtSeqFile = writeOrfExt2fileOnStream(orfhits, seq)

	#subject = writeDNA2fileOnStream(seqid, seq)
	# write full-length dna sequence into a temporary file to be called by makeblastdb
	fp = tempfile.NamedTemporaryFile(mode='w', delete=False)
	writeDNA2file(fp, seqid, seq)
	fp.close()
	'''
	# make blast database
	#blastdb = os.path.join(constants.dir4blastout, org, fileid+'.fna')
	blastdb = os.path.join(constants.dir4blastout, org, '.'.join([fileid,seqid,'fna']))
	tools.makedir(os.path.dirname(blastdb))
	tools.seq2blastdb(fp.name, blastdb)
	os.remove(fp.name)
	'''

	# blastn(megablast) searches ORF extended sequences against genome dna sequence
	# Note: each ORF extended sequence must be longer than the corresponding IS element with 
	# 	ORF as transposase in order that the local alignment resulted from blastn can be
	#	defined as the alignment between multiple full-length IS element copies.
	#blastOut4orfExt = os.path.join(constants.dir4blastout, org, os.path.basename(blastdb)+'.out')
	'''
	blastOut4orfExt = blastdb+'.out'
	tools.blastnSearch(orfExtSeqFile, blastdb, blastOut4orfExt, strand='both', task='megablast')
	os.remove(orfExtSeqFile)
	for ext in ('.nhr', '.nin', '.nsq'):
		os.remove(blastdb+ext)
	'''
	query = orfExtSeqFile
	norfhits = len(orfhits)
	if constants.nthread < norfhits:
		nthreads = constants.nthread
	else:
		nthreads = norfhits
	#blastOut4orfExt, err = tools.doBlastnOnStream(query, blastdb, strand='both', task='megablast', 
	blastOut4orfExt, err = tools.doBlastn2seqOnStream(query, fp.name, strand='both', task='megablast', 
			perc_ident=constants.SIM4ISO)
	if len(err) > 0:
		#e = 'Blastn ISs in {} against {}: {}'.format(seqid, db, err)
		e = 'Blastn ISs in {} against {}: {}'.format(seqid, seqid, err)
		raise RuntimeError(e)

	# get copy number of ORF extended sequence
	ispairs = {}
	# ispairs: {qseqid:[hit, ...]}
	# hit: {'qseqid':qseqid, 'sseqid':sseqid, 'orfBegin':orfBegin, 'orfEnd':orfEnd, 'length':length, ...}
	for k, g in itertools.groupby(
			sorted(tools.getBlastResult4dnaOnStream(blastOut4orfExt), key=lambda x: x['qseqid']), 
			key=lambda x: x['qseqid']):
		ispairs[k] = list(g)
		ispairs[k].sort(key = lambda x: x['length'], reverse = True)
	
	# orfhits: [orfhit, ..., orfhit]
	# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
	# orf: (accid, begin, end, strand), example, ('NC_000915.1', 20, 303, '+')
	for qseqid, g in ispairs.items():
		orfstr4is = '_'.join(qseqid.rsplit('_', maxsplit=3)[1:])
		for orfhit in orfhits:
			orfstr = '_'.join([str(item) for item in orfhit[0][1:]])
			if orfstr == orfstr4is:
				break
		for ispair in g:
			ispair['orfhit'] = orfhit
	return ispairs

# Return mhits:
# mhits: {seqid: hits, ..., seqid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'bd': bd}
# orf: (seqid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# bd: [start, end], boundary of hit (IS element)
# 
# mispairs: {seqid: ispairs, ..., seqid: ispairs}
# ispairs: {qseqid: g, ..., qseqid: g}
# g: [ispair, ..., ispair]
# ispair: {'qseqid':qseqid, 'length':length, 'qstart':qstart, 'qend':qend, 'sstart':sstart, 'send':send,
#		'nident':nident, 'qlen':qlen, 'slen':slen, 'pident':pident,
#		'orfBegin':orfBegin, 'orfEnd':orfEnd, 'orfhit':orfhit, ...}
# 1. define IS boundary by TIR if TIR is available in an IS element
# 2.1 define IS boundary by alignment if no TIR is available in a multiple-copy IS element and alignment 
#	does not span/intersect multiple Tpase ORFs; else
# 2.2 define IS boundary by ORF
# 3. define IS boundary by ORF if no TIR is available in a single-copy IS element
def mTIR2hits4ispair(mispairs, mTIR, morfhitsNeighbors):
	mhits = {}
	for seqid, ispairs in mispairs.items():
		if len(ispairs) == 0:
			continue
		hits = []
		for qseqid, g in ispairs.items():
			orfhitsNeighbors = morfhitsNeighbors[seqid]
			hit = {}
			orfhit = g[0]['orfhit']
			orf = orfhit[0]
			orfStr = '_'.join([str(item) for item in orf])
			hit['orf'] = orf
			hit['hmmhit'] = orfhit[1:]
			if orfStr not in mTIR:
				hit['tirs'] = []
			else:
				hit['tirs'] = mTIR[orfStr][2]

			ncopy = len(g)

			# IS element with TIR, with boundary defined by the first TIR
			if len(hit['tirs']) > 0 and len(hit['tirs'][0]) > 0:
				tir = hit['tirs'][0]
				hit['bd'] = [tir[-6], tir[-3]]
			# multiple-copy IS element without TIR, with boundary defined by 
			# the longest blast alignment, namely, g[1] because g[0] is the 
			# alignment of query and itself.
			elif ncopy > 1:
				#hit['bd'] = [g[1]['qstart'], g[1]['qend']]
				qstart, qend = g[1]['qstart'], g[1]['qend']

				# if aligned region spans two or more Tpases, eg. composite transposon, 
				# the current hit in the aligned region is trimmed to the tpase ORF.
				if constants.splitAlign2orf == True:
					before = orfhitsNeighbors[orf][0]
					after = orfhitsNeighbors[orf][1]
					if (before != None and qstart <= before[0][2]) or (after != None and qend >= after[0][1]):
						qstart, qend = orf[1], orf[2]
				'''
				before = orfhitsNeighbors[orf][0]
				after = orfhitsNeighbors[orf][1]
				if (before != None and qstart <= before[0][2]) or (after != None and qend >= after[0][1]):
					qstart, qend = orf[1], orf[2]
				'''
				hit['bd'] = [qstart, qend]
			# single-copy IS element without TIR, with boundary defined by ORF
			else:
				hit['bd'] = [orf[1], orf[2]]

			# add copy number info to hit (IS element)
			hit['occurence'] = {}
			hit['occurence']['ncopy4is'] = ncopy
			hit['occurence']['ncopy4orf'] = 0
			hit['occurence']['sim4orf'] = 0.0
			hit['occurence']['sim4is'] = 0.0

			hits.append(hit)
		if len(hits) > 0:
			hits.sort(key = lambda x: x['bd'][0])
			mhits[seqid] = hits
	return mhits

def getFullIS(mOrfHits, mDNA, maxDist4ter2orf, minDist4ter2orf, morfhitsNeighbors):
	mispairs = {}
	margs = []
	for seqid, orfHits in mOrfHits.items():
		if len(orfHits) == 0:
			continue
		args = (seqid, orfHits, mDNA[seqid])
		margs.append(args)
	'''
	for args in margs:
		mispairs[seqid] = getFullIS4seqOnStream(args)
	'''

	nseq = len(margs)
	'''
	if nseq > constants.nproc:
		nproc = constants.nproc
	else:
		nproc = nseq
	'''
	if nseq > constants.nthread:
		nthread = constants.nthread
	else:
		nthread = nseq

	#with concurrent.futures.ProcessPoolExecutor(max_workers = nproc) as executor:
	with concurrent.futures.ThreadPoolExecutor(max_workers = nthread) as executor:
		future2args = {executor.submit(getFullIS4seqOnStream, args): args for args in margs}
		for future in concurrent.futures.as_completed(future2args):
			args = future2args[future]
			try:
				ispairs = future.result()
			except Exception as e:
				print('{} generated an exception: {}'.format(args[0], e))
			else:
				mispairs[args[0]] = ispairs

	mInput4ssw, mboundary = is_analysis.prepare4ssw2findIRbyDNAbyFar4ispair(
			mispairs, mDNA, maxDist4ter2orf, minDist4ter2orf, morfhitsNeighbors)

	#filters = constants.filters4ssw4flankingAndISmax
	#filters = constants.filters4ssw4flanking
	filters = constants.filters4ssw4trial
	#filters = constants.filters4ssw4oasis
	#filters = constants.filters4ssw_default
	TIRfilters = []
	for filter in filters:
		TIRs = is_analysis.findIRbySSW(mInput4ssw, filter)
		TIRfilters.extend([(TIR, filter) for TIR in TIRs])

	bestTIRfilters = is_analysis.checkTIRseq(TIRfilters)

	# keep only unique TIRs for each IS element under one filter
	mTIR = is_analysis.independentTIRwithScore(bestTIRfilters)

	# Convert boundary numbering in short sequence segment to boundary numbering in original full sequence
	mTIR = is_analysis.restoreBoundary4tir(mTIR, mboundary)

	# add TIR info to ORF hit:
	# 1. define IS boundary by TIR if TIR is available in an IS element
	# 2.1 define IS boundary by alignment if no TIR is available in a multiple-copy IS element and alignment 
	#	does not span/intersect multiple Tpase ORFs; else
	# 2.2 define IS boundary by ORF
	# 3. define IS boundary by ORF if no TIR is available in a single-copy IS element
	mHits = mTIR2hits4ispair(mispairs, mTIR, morfhitsNeighbors)

	return mHits


# choose the tir between mHitsByNear and mHitsByFar:
# rule: tir near Tpase ORF is used if tir is available in mHitsByNear, else 
#	tir found in mHitsByFar is used.
# mhits: {seqid: hits, ..., seqid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'bd': bd, 'occurence': occurence}
# orf: (seqid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# bd: [start, end], boundary of hit (IS element)
# occurence: {'ncopy4orf': ncopy4orf, 'sim4orf': sim4orf, 'ncopy4is': ncopy4is, 'sim4is': sim4is}
# 
def chooseHits(mHitsByNear, mHitsByFar):
	mhits = {}
	for accid, hitsByNear in mHitsByNear.items():
		hitsByFar = mHitsByFar[accid]
		hits = []
		hitsByNear.sort(key = lambda x: x['orf'][1])
		hitsByFar.sort(key = lambda x: x['orf'][1])
		for hitpair in zip(hitsByNear, hitsByFar):
			'''
			if len(hitpair[0]['tirs']) > 0:
				hit = hitpair[0]
			elif len(hitpair[1]['tirs']) > 0:
				hit = hitpair[1]
				print('tir not in near region but in far region', hit)
			else:
				hit = hitpair[0]
			'''
			# sort two hits by score of tir, and get the hit with greater score
			# Note: the hitpair[0] will be returned if two hits have the same score.
			hit = sorted(hitpair, 
					key = lambda x: tools.irScore(x['tirs'][0]) if len(x['tirs'])>0 else 0, 
					reverse=True)[0]

			hits.append(hit)
			#print('hello choose hit', hit)
		hits.sort(key = lambda x: x['bd'][0])
		mhits[accid] = hits
	return mhits

# Remove short hit
def refineHits(mHits):
	evalue_cutoff = constants.min4evalue
	evalue4singleCopy = constants.evalue4singleCopy
	irSim4singleCopy = constants.irSim4singleCopy
	mhitsCopy = {}
	for accid in mHits.keys():
		hitsCopy = []
		for hit in mHits[accid]:
			familyName = hit['hmmhit'][0]
			if '|' in familyName:
				familyCluster = familyName.split('|',1)[0]
			else:
				familyCluster = familyName
			family, cluster = familyCluster.rsplit('_', 1)
			minLen4is = constants.minMaxLen4is[family][0]
			begin, end = hit['bd']
			isLen = end - begin + 1
			if isLen < minLen4is:
				print('remove short hit (partial IS element)', isLen, hit['bd'], hit['orf'])
				continue

			#if hit['hmmhit'][2] > evalue_cutoff:
			#	continue

			# test evalue and number of Tpase copies (IS copies)
			if hit['hmmhit'][2] > evalue4singleCopy and hit['occurence']['ncopy4is'] < 2:
				# filter out hits without TIR
				if len(hit['tirs']) == 0:
					continue
				# filter out hits with gaps in TIR (alignment of left hand rigth hand TIR sequences)
				elif hit['tirs'][0][3] > 0:
					continue
				# filter out hits with irId/irLen < irSim4singleCopy (default 0.85)
				elif hit['tirs'][0][1]/hit['tirs'][0][2] < irSim4singleCopy:
					continue

			hitsCopy.append(hit)
		if len(hitsCopy) == 0:
			print('Warning: no valid hit found for {}'.format(accid))
			continue
		# sort hit by begin of orf
		#hitsCopy.sort(key=lambda x: x['orf'][1])
		hitsCopy.sort(key=lambda x: x['bd'][0])
		mhitsCopy[accid] = hitsCopy
	
	newkeys = mhitsCopy.keys()
	for k in mHits.keys():
		if k not in newkeys:
			print('Warning: no valid hit after removing short IS element candidate for', k)
	return mhitsCopy


# Attach score of IS elements to hits
#
# mhits: {accid: hits, ..., accid: hits}
# hits: [hit, ..., hit]
# hit: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'occurence': occurence}
# 
# mhitsNew: {accid: hitsnew, ..., accid: hitsnew}
# hitsnew: [hitnew, ..., hitnew]
# hitnew: {'orf': orf, 'tirs': tirs, 'hmmhit': hmmhit, 'occurence': occurence, 'isScore': isScore}
# orf: (accid, begin, end, strand)
# tirs: [tir, ..., tir]
# tir: (score, irId, irLen, nGaps, start1, end1, start2, end2, seq1, seq2)
# hmmhit: (familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
# occurence: {'ncopy4orf': ncopy4orf, 'sim4orf': sim4orf, 'ncopy4is': ncopy4is, 'sim4is': sim4is}
# ncopy4orf: copy number of the specific Tpase ORF with sim > constants.sim4iso in same DNA sequence
# ncopy4is: copy number of the specific IS element with sim > constants.sim4iso in same DNA sequence
# sim4orf: Tpase ORF with identicalBases/lengthOfAlignment > sim are regarded as the same Tpase
# sim4is: IS elements with identicalBases/lengthOfAlignment > sim are regarded as the same IS element
# isScore: {'evalue': score4evalue, 'tir': score4tir, 'dr': score4dr, 'occurence': score4occurence, 'score': isScore,
#		'ncopy4orf': ncopy4orf, 'ncopy4is': ncopy4is}
#
def scoreHits(mhits):
	mhitsNew = {}
	for accid in mhits:
		hits = []
		for item in mhits[accid]:
			hit = {}
			isScore = {}
			isScore['evalue'], isScore['tir'], isScore['dr'], isScore['occurence'], isScore['irSim'], isScore['ncopy4orf'], isScore['ncopy4is'] = scoreHit(item)

			isScore['score'] = isScore['evalue'] + isScore['tir'] + isScore['dr'] + isScore['occurence']

			# Filter out hits with isScore < constants.isScore
			#if isScore['score'] < constants.isScore:
			#	continue

			hit['isScore'] = isScore
			hit['orf'] = item['orf']
			hit['hmmhit'] = item['hmmhit']
			hit['tirs'] = item['tirs']
			hit['occurence'] = item['occurence']
			hit['bd'] = item['bd']
			hits.append(hit)
		mhitsNew[accid] = hits
	return mhitsNew

def scoreHit(hit):
	# score for full_sequence_E-value of hmm hit
	# Option1:
	'''
	if hit['hmmhit'][2] > 0:
		# log(x), x > 0 
		score4evalue = - math.log(hit['hmmhit'][2], 10)
	else:
		# if x == 0 or close to zero like 10**(-sys.float_info.min_10_exp)
		score4evalue = - sys.float_info.min_10_exp
	'''

	# Option2:
	#score4evalue =  score4evalue * score4evalue

	# Option3:
	#scale4evalue = 3
	#score4evalue =  score4evalue * scale4evalue
	# Do not need score4evalue
	score4evalue = 0.0

	# Score for TIR.
	# We simply use the first tir if multiple tirs available for a hit.
	if len(hit['tirs']) > 0 and len(hit['tirs'][0]) > 0:
		score, irId, irLen = hit['tirs'][0][:3]
		irSim = irId/irLen
		'''
		#if irSim < constants.minIrIdentity:
		if(irSim < constants.optIrIdentity
			or ((irLen < constants.stringentShortestIR or irLen > constants.stringentLongestIR) 
				and irSim < constants.stringentIrIdentity)):
			score4tir = 0
		else:
			score4tir = score * irSim * irSim
		'''
	else:
		irSim = 0
		score4tir = 0
	# Do not count tir.
	score4tir = 0

	# score for DR
	score4dr = 0

	# score for occurence of IS elements in same DNA sequence
	# The score will be higher when higher sim is used to define same IS element (isoform)
	# Here, we set score4occurence = 0 if only one copy was found.
	# Note: it might be better to weight full IS (Tpase+TIR+DR) copy higher than Tpase copy.
	# score4occurence = Fbeta * scale4is * sim4is
	# Here, Fbeta = (1 + beta**2) * (ncopy4is+ncopy4orf-1)**2 / (ncopy4is + beta**2 * ncopy4orf), 
	# namely, corrected F beta measure which is borrowed from Fbeta in statistics.
	# Fbeta attaches beta times as much importance to ncopy4is as ncopy4orf.
	# In our practice, we use beta = 2, let F2 = 5 * (ncopy4is+ ncopy4orf-1)**2 / (ncopy4is + 4*ncopy4orf)
	#
	ncopy4is = hit['occurence']['ncopy4is']
	ncopy4orf = hit['occurence']['ncopy4orf']
	'''
	sim4is = hit['occurence']['sim4is']
	sum = (ncopy4is + ncopy4orf -1)
	f2 = 5 * sum * sum / (ncopy4is + 4*ncopy4orf)
	scale4is = 10
	#scale4is = 30
	score4occurence = f2 * scale4is * sim4is
	#score4occurence = (ncopy4is + ncopy4orf) * scale4is * sim4is

	#score = score4evalue + score4tir + score4dr + score4occurence
	'''
	score4occurence = 0.0

	return (score4evalue, score4tir, score4dr, score4occurence, irSim, ncopy4orf, ncopy4is)


# Input: fileids
# fileids: [(fileid, org), ...], e.g. NC_000913, SRS078176.scaffolds
# filenames: [(filename,org), ...], e.g. NC_000913.fna, SRS078176.scaffolds.fa
#
# Return a list of hmmHitsFiles
# tblout_list: [hmmHitsFile, ...]
# tbloutFile: created by hmmer (phmmer or hmmsearch) run as the following command,
#	phmmer --tblout phmmerHitsFile --max --noali --cpu nthread seqFile databaseFile
# seqFile: profile HMM models file, created by hmmbuild in HMMer package
# databaseFile: proteome file in which multiple protein amino acid sequence are placed in FASTA format
def prepare4tblout_list(hmm_path, fileids):
	tblout_list = []
	hmmFile = constants.file4clusterHMM
	hmmFileName = os.path.basename(hmmFile)
	faaFile = constants.file4clusterSeqFile4phmmer
	faaFileName = os.path.basename(faaFile)
	for item in fileids:
	#for item in filenames:
		filename, org = item
		# For result returned by hmmsearch (hmm against protein database)
		#if os.path.isfile(hmmFile):
		fileName = '.'.join([hmmFileName, filename, 'faa'])
		tblout = os.path.join(hmm_path, org, fileName)
		if os.path.isfile(tblout):
			if os.stat(tblout).st_size == 0:
				print('Empty file:', tblout)
			else:
				tblout_list.append(tblout)
		else:
			print('No such file', tblout)

		# for result returned by phmmer (protein sequence against protein database)
		#if os.path.isfile(faaFile):
		fileName = '.'.join([faaFileName, filename, 'faa'])
		tblout = os.path.join(hmm_path, org, fileName)
		if os.path.isfile(tblout):
			if os.stat(tblout).st_size == 0:
				print('Empty file:', tblout)
			else:
				tblout_list.append(tblout)
		else:
			print('No such file', tblout)
	return tblout_list

def outputHits(hits, outfile):
	lines = []
	for hit in hits:
		lines.append(hit[1])
	fp = open(outfile, 'w')
	fp.write(''.join(lines))
	fp.close()

def pred(args):
	print('pred begins at', datetime.datetime.now().ctime())

	fileids = []
	# fileids: [(fileid, org), ...]
	filenames = []
	# filenames: [(filename,org), ...], e.g. NC_000913.fna, SRS078176.scaffolds.fa
	#
	# mDNA:	{seqid: (org, fileid, sequence), ..., seqid: (org, fileid, sequence)}
	mDNA = {}
	dnaFiles = tools.rdDNAlist(args['dna_list'])
	for item in dnaFiles:
		file, org = item
		filename = os.path.basename(file)
		#fileid = filename.rsplit('.', 1)[0]
		fileid = filename
		fileids.append((fileid, org))

		# seqs: [seq, ...]
		# seq: (id, seq)
		seqs = tools.getFasta(file)
		if len(seqs) > 0 and len(seqs[0]) > 0:
			#mDNA[seqs[0][0]] = (org, fileid, seqs[0][1])
			for seq in seqs:
				mDNA[seq[0]] = (org, fileid, seq[1])
		else:
			print('Warning: no sequence found in', file)
	fileids.sort(key = operator.itemgetter(0))

	# Get hmmsearch hits and write the sorted hits into a file

	if 'hitsFile' in args.keys():
		tblout_list = args['hitsFile']
	else:
		hmm_path = args['path_to_hmmsearch_results'].strip()
		tblout_list = prepare4tblout_list(hmm_path, fileids)
	if len(tblout_list) == 0:
		print('No results returned by HMM search was found for sequences in', args['dna_list'])
		return 0

	#print('Processing tblout files at', datetime.datetime.now().ctime())	
	mtblout_hits_sorted = []
	for tblout in tblout_list:
		#seqids, tblout_hits_sorted = process_tblout(tblout)
		tblout_hits_sorted = process_tblout(tblout)
		# seqids: {}, set of sequence identifiers in a dnaFile with multiple sequences included
		#
		# tblout_hits_sorted: [hit, ...]
		# hit: [best1domainEvalue, line, compoundID, queryName, best1domainEvalue, overlapNumber]
		# best1domainEvalue: float, evalue for best 1 domain, refer to hmmsearch manual for details
		# line: whole line ending with '\n' in hmmhitsFile created by hmmsearch
		# compoundID: the first string ending with space character in protein sequence (.faa) file 
		#	created by FragGeneScan, e.g. 'gi|256374160|ref|NC_013093.1|_6781872_6782144_-',
		#	'C2308936_1_1062_-', 'SRS078176_LANL_scaffold_9132_3106_4113_+'
		# queryName: name of HMM model in profile HMM model file created by hmmsearch or phmmer, 
		#	e.g. 'IS200_IS605_0.faa', 'IS200/IS605_1|IS200/IS605|IS1341|ISBLO15|'
		# overlap: integer, overlap number, how many of envelopes overlap other envelopes; 
		#	be careful when ov > 0refer to hmmsearch manual for details

		if len(tblout_hits_sorted) == 0:
			print('Warning: no hit returned by HMM search in', tblout)
			continue
		#mtblout_hits_sorted.append((seqids, tblout_hits_sorted))
		mtblout_hits_sorted.append(tblout_hits_sorted)

	#print('Finish processing tblout files at', datetime.datetime.now().ctime())	
	
	#print('Combine and sort hits returned by hmmsearch and phmmer at', datetime.datetime.now().ctime())
	# Combine hits returned by hmmsearch and phmmer against the same database.
	# mtblout_hits_sorted: [tblout_hits_sorted, ...]
	# tblout_hits_sorted: [hit, ..., hit]

	hitsNew = []
	# hitsNew: [(seqid, hit)]
	# itertools.chain.from_iterable: Flatten list of lists
	for hit in itertools.chain.from_iterable(mtblout_hits_sorted):
		seqid = hit[2].rsplit('_', maxsplit=3)[0] 
		hitsNew.append((seqid, hit))
	mhits = []
	# mhits: [(seqid, hits_sorted) ...]
	hitsNew.sort(key=operator.itemgetter(0))
	for seqid,idhitg in itertools.groupby(hitsNew, key=operator.itemgetter(0)):
		# idhitg: like [(seqid,hit), ...]
		hits = [idhit[1] for idhit in idhitg]
		
		# Sort hits in one protein database (one translated DNA sequence e.g. one genome sequence)
		# If sorted type is changed here, please change e_value_type in 
		# refine_hmm_hits_evalue(tblout_hits_sorted, e_value) immediately
		#
		# 5 , 0 and 4 correspond to overlap number, best 1 domain E-value and full sequence E-value, respectively
		if SORT_BY == 0:
			hits_sorted = sorted(hits, key = operator.itemgetter(0))
		elif SORT_BY == 4:
			# hmmsearch report hits ranked by full sequence E-value for each HMM model.
			# We rank hits from all HMM modles in one hmmsearch report file in one sorting.
			# Note: mutliple family HMM models exist in each tbl_out file, see any tbl_out file
			# refer to ftp://selab.janelia.org/pub/software/hmmer3/3.1b2/Userguide.pdf
			hits_sorted = sorted(hits, key = operator.itemgetter(4))

		mhits.append((seqid, hits_sorted))

	'''
	for seqid, g in itertools.groupby(sorted(mtblout_hits_sorted, key = operator.itemgetter(0)), 
			key = operator.itemgetter(0)):
		# group by seqids
		hits = []
		for idHits in g:
			hits.extend(idHits[1])

		# Sort hits in one protein database (one translated DNA sequence e.g. one genome sequence)
		# If sorted type is changed here, please change e_value_type in 
		# refine_hmm_hits_evalue(tblout_hits_sorted, e_value) immediately
		#
		# 5 , 0 and 4 correspond to overlap number, best 1 domain E-value and full sequence E-value, respectively
		if SORT_BY == 0:
			hits_sorted = sorted(hits, key = operator.itemgetter(0))
		elif SORT_BY == 4:
			# hmmsearch report hits ranked by full sequence E-value for each HMM model.
			# We rank hits from all HMM modles in one hmmsearch report file in one sorting.
			# Note: mutliple family HMM models exist in each tbl_out file, see any tbl_out file
			# refer to ftp://selab.janelia.org/pub/software/hmmer3/3.1b2/Userguide.pdf
			hits_sorted = sorted(hits, key = operator.itemgetter(4))

		mhits.append((seqid, hits_sorted))
	'''
	#print('Finish combining and sorting hits returned by hmmsearch and phmmer at', datetime.datetime.now().ctime())

	mtblout_hits_sorted = mhits
	# mtblout_hits_sorted: [(seqid, tblout_hits_sorted), ...]
	# seqid: character sting
	# tblout_hits_sorted: [hit, ..., hit]

	# Output sorted hits for each accid
	'''
	path2hits = os.path.dirname(tblout_list[0])
	for idhits in mtblout_hits_sorted:
		outfile = os.path.join(path2hits, idhits[0] + '.sorted')
		outputHits(idhits[1], outfile)
	'''


	# E-value cutoff for filtering hits returned by HMM search
	e_value = constants.evalue2filterHMMhits
	

	#print('Refine hits for each DNA sequence', datetime.datetime.now().ctime())
	# Refine hits from genome sequences
	# ! Keep only the best family hit from the different IS family HMM searches.
	# ! Filter the hits by e-value cutoff
	mtblout_hits_sorted_refined = []
	for seqid_hits in mtblout_hits_sorted:
		seqid, hits_sorted = seqid_hits

		# remove redundant hits, keeping only the best family hit from the different 
		# IS family HMM searches.
		hits_sorted = refine_hmm_hits(hits_sorted)

		# remove non-significant hits with E-value > cutoff
		if hits_sorted == None or len(hits_sorted) == 0:
			e = 'No hit was found for {} {}'.format(seqid, seqid_hits)
			print(e)
			return

		hits_sorted_refined = refine_hmm_hits_evalue(hits_sorted, e_value)
		if len(hits_sorted_refined) == 0:
			print('Warning: no significant hit with E-value <= {} found for {}'.format(
				e_value, seqid))
			continue
		mtblout_hits_sorted_refined.append((seqid, hits_sorted_refined))
	#print('Finish refining hits for each DNA sequence', datetime.datetime.now().ctime())

	mtblout_hits_sorted = mtblout_hits_sorted_refined


	# Find TIR for ORF of each hit
	#
	# mtblout_hits_sorted:	[(seqid, hits_sorted_refined), ..., (seqid, hits_sorted_refined)]
	# hits_sorted_refined:	[hit, ..., hit]
	# hit:			(best_1_domain_E-value, hit_line, compound_ID, IS_family_name, full_sequence_E-value, overlap_number)
	# best_1_domain_E-value: float, best 1 domain E-value
	# hit_line:		string, hit line
	# compound_ID:		string, compound ID, for example, gi|15644634|ref|NC_000915.1|_923867_924196_+
	# IS_family_name:	string, query name, name of query sequence or profile, for example, IS1.long.pep.all
	# full_sequence_E-value: float, full sequence E-value
	# overlap_number:	int, overlap number, how many of envelopes overlap other envelopes; pay special attention to hit with ov > 0
	#
	# morfHits: {seqid: orfHits, ..., seqid: orfHits}
	# orfHits: [orfhit, ..., orfhit]
	# orfhit: (orf, familyName, best_1_domain_E-value, full_sequence_E-value, overlap_number)
	# orf: (seqid, begin, end, strand), example, ('gi|15644634|ref|NC_000915.1|', 20, 303, '+')

	#print('Convert hits to orfHits at', datetime.datetime.now().ctime())
	mOrfHits = convertHits2orfHits(mtblout_hits_sorted)
	#print('Finish converting hits to orfHits at', datetime.datetime.now().ctime())
	
	# Merge orfs if two orfs with distance < maxDistBetweenOrfs
	maxDistBetweenOrfs = constants.maxDistBetweenOrfs
	mOrfHits, morfsMerged = mergeOrfs(mOrfHits, maxDistBetweenOrfs)


	#print('hitNeighors() begins at', datetime.datetime.now().ctime())
	# search TIR for multiple-copy IS element candidate and single-copy IS element candidate
	minDist4ter2orf = constants.minDist4ter2orf
	morfhitsNeighbors = hitNeighors(mOrfHits)

	#print('getFullIS() begins at', datetime.datetime.now().ctime())
	# look for tir in the neighboring region of Tpase ORF in case of single-copy IS
	maxDist4ter2orf = constants.outerDist4ter2tpase[0]
	mHitsByNear = getFullIS(mOrfHits, mDNA, maxDist4ter2orf, minDist4ter2orf, morfhitsNeighbors)

	# look for tir in the widen region of Tpase ORF in case of single-copy IS
	maxDist4ter2orf = constants.outerDist4ter2tpase[1]
	mHitsByFar = getFullIS(mOrfHits, mDNA, maxDist4ter2orf, minDist4ter2orf, morfhitsNeighbors)

	# choose the tir between mHitsByNear and mHitsByFar:
	# rule: keep tir near Tpase ORF if tir found in mHitsByNear, else use
	#       tir found in mHitsByFar.
	mHits = chooseHits(mHitsByNear, mHitsByFar)
	#mHits = mHitsByFar

	#for hits in mHits.values():
	#	for hit in hits:
	#		print('raw hit', hit['bd'], hit['orf'], hit['hmmhit'], hit['occurence'], hit['tirs'])

	# remove hits that are partial IS elements identified by length, evalue and irId/irLen
	if constants.removeShortIS == True:
		mHits = refineHits(mHits)

	# remove redundant IS elements with same boundary and same TIR
	mHits = removeRedundantIS(mHits)
	mHits = removeOverlappedHits(mHits)

	# Calculate socore for each hit and then attach score to hit
	#print('Begin scoring hits at', datetime.datetime.now().ctime())
	mHits = scoreHits(mHits)
	#print('Finish scoring hits at', datetime.datetime.now().ctime())

	#--------------------------
	# Output predictions, mHits

	#print('Begin reading protein database at', datetime.datetime.now().ctime())
	# Get full lists of genes for each genome sequence
	# proteomes: {seqid: (filename, genes), ...}
	# genes: {cdsid: seq, ...}
	# cdsid: example, SRS075404_LANL_scaffold_1_1_414_+, C3691328_7626_8378_-
	# seq: protein sequence
	proteomes = {}
	path_to_proteome = args['path_to_proteome'].strip()
	# fileids: [(fileid, org), ...], e.g. NC_000913.fna, SRS078176.scaffolds.fa
	for item in fileids:
		filename, org = item
		#proteome_file = os.path.join(path_to_proteome, org, fileid + '.fna.faa')
		proteome_file = os.path.join(path_to_proteome, org, filename + '.faa')
		if os.stat(proteome_file).st_size == 0:
			print('Empty file:', proteome_file)
			continue
		#seqid, genes = tools.getcds(proteome_file)
		# cdss: [(seqid, cdsid,seq), ...]
		# seqid: sequence id, e.g. SRS075404_LANL_scaffold_1, C3691328
		# cdsid: cds identifier, e.g. SRS075404_LANL_scaffold_1_1_414_+, C3691328_7626_8378_-
		# seq: protein sequence
		cdss = tools.getcds(proteome_file)
		# group cdss by seqid
		cdss.sort(key=operator.itemgetter(0))
		for seqid,cdsgroup in itertools.groupby(cdss, key=operator.itemgetter(0)):
			genes = {seqid_cdsid_seq[1]:seqid_cdsid_seq[2] for seqid_cdsid_seq in cdsgroup}
			proteomes[seqid] = (filename, genes)
	#print('Finish reading protein database at', datetime.datetime.now().ctime())

	# Output IS element list and sequence for each DNA sequence into .out, .gff and .fna files, respectively.
	#
	# mDNA:	{seqid: (org, fileid, sequence), ..., seqid: (org, fileid, sequence)}
	orgfiles = set(os.path.join(v[0],v[1]) for v in mDNA.values()) 
	norgfiles = len(orgfiles)
	# mHits: {accid: hits, ..., accid: hits}
	# hits: [hit, ..., hit]
	if sum([len(hits) for hits in mHits.values()]) == 0:
		print('No IS element was identified for', sorted(mHits.keys()))
		print('End in pred', datetime.datetime.now().ctime())
		return 0

	if norgfiles > 1:
		outputIndividual(mHits, mDNA, proteomes, morfsMerged)
	elif norgfiles == 1:
		# output ISs in all sequences into one file
		if len(mHits) > 0:
			outputIS4multipleSeqOneFile(mHits, mDNA, proteomes, morfsMerged, orgfiles.pop())
		else:
			print('No IS element was found for {}'.format(mHits.keys()))
	else:
		e = 'Error: cannot get organism name (directory name holding genome sequence FASTA file) and FASTA sequence file name!'
		raise RuntimeError(e)

	# Output predictions, mHits
	#--------------------------

	print('End in pred', datetime.datetime.now().ctime())


if __name__ == "__main__":
	descriptStr = 'Rerank and filter hits in hmmsearch output produced by --tblout output option, ranked by E-value (increasing E-value). A typical invocaltion would be: python3 pred.py dna.list /home/data/insertion_sequence/output4FragGeneScan1.19_illumina_5 /home/data/insertion_sequence/output4hmmsearch_illumina_5'

	parser = argparse.ArgumentParser(description = descriptStr)

	helpStr = 'input file containing the list of DNA sequence files, one file per line'
	parser.add_argument('dna_list', help = helpStr)

	helpStr = 'directory holding files produced by FragGeneScan'
	parser.add_argument('path_to_proteome', help = helpStr)

	helpStr = 'directory holding files produced by hmmsearch with options \'--tblout output option\''
	parser.add_argument('path_to_hmmsearch_results', help = helpStr)

	args = parser.parse_args()

	args4pred = {
			'dna_list': args.dna_list,
			'path_to_proteome': args.path_to_proteome,
			'path_to_hmmsearch_results': args.path_to_hmmsearch_results,
			}

	pred(args4pred)

