from pathlib import Path
from abc import ABC, abstractmethod

import pandas as pd

## Dataframe style expected in the main pipeline.
# If it follows this, it can be used to add audio path to rows
# audio_schema = pa.DataFrameSchema({
# 	# JMdict ID
# 	"id": pa.Column(int),
# 	"audio_path": pa.Column(str),
# })

class EtlAudio(ABC):
	def download(self):
		"""Any data that needs downloading so it accessible locally.
		Optional, e.g. if data from source needs to be obtained manually
		"""

	@abstractmethod
	def extract(self) -> pd.DataFrame:
		"""dataframe where rows correspond to word/reading combo.
		Should include the audio path

		Returns
		-------
		pd.DataFrame
			_description_
		"""
		pass

	# @pa.check_types
	@abstractmethod
	def lookup(self, audiodf: pd.DataFrame, jmdict: pd.DataFrame) -> pd.DataFrame:
	# def lookup(self, audiodf: pd.DataFrame, jmdict: pd.DataFrame) -> pa.typing.DataFrame[audio_schema]:
		"""Take the audio df and add the jmdict id column.
		Now ready for use in the main pipleline

		Parameters
		----------
		audiodf: pd.DataFrame
			dataframe with all the rows necessary to perform an ID lookup in the jmdict, along with the path of the audio file

		jmdict : pd.DataFrame
			the jm dictionary, used for matching against and finding the associated id

		Returns
		-------
		pa.typing.DataFrame[audio_schema]
			pipeline-ready audio-path dataframe. Expects column 1: int: jmdict_seq. Column 2: str: audio_path
		"""
		pass
	
	# @pa.check_types
	def enrich(self, audio_df: pd.DataFrame, main_df: pd.DataFrame) -> pd.DataFrame:
		"""Adds audio_path column to the given dataframe, merged via jmdict id probably

		Parameters
		----------
		audio_df : pd.DataFrame
			generated from the rest of the functions in this class. Has a column "jmdict_seq" (int) and an "audio_path" (str) column
		main_df : pd.DataFrame
			Expects to have a "jmdict_seq" (int) column, of which word in the jmdict the row corresponds to

		Returns
		-------
		pd.DataFrame
			main_df with additional audio_path (str) column, the location to find the audio for this given word
		"""
		df = main_df.merge(
			audio_df,
			on="jmdict_seq",
			how="left",
		)
		return df


	def run(self, jmdict: pd.DataFrame, main_df: pd.DataFrame) -> pd.DataFrame:
		self.download()
		df = self.extract()
		df = self.lookup(df, jmdict)
		df = self.enrich(df, main_df)
		return df