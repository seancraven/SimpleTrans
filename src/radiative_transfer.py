# %%
"""
This file uses the database built by the 
"""
import sqlite3
from typing import Tuple

import isa
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from plank import plank_nu
from tqdm import tqdm


# %


def fetch_od_from_db(
    connection: sqlite3.Connection,
    gas: str,
    alt_range: Tuple[float, float],
    wave_no_range: Tuple[float, float],
    verbose: bool,
) -> Tuple[dict[int:ArrayLike], ArrayLike]:
    """
    Returns a smoothed dict of optical depths, where the key is the
    altitude.
    Only returns values in the intervals:
    [wave_no_min, wavenumber_max], [alt_min, alt_max].
    Additionally, returns the bins in which the values are put into.

    Args:
        verbose:
        alt_range:
        wave_no_range:
        gas: gas name, must be in database.
        connection: Database Connection, with optical depths.


    Returns:

    """
    wave_no_min, wave_no_max = wave_no_range
    alt_min, alt_max = alt_range

    sql_gas_query = f"SELECT mol_id, mol_name FROM gases WHERE mol_name = '{gas}';"
    gas_df = pd.read_sql_query(sql_gas_query, connection)
    gas_id = gas_df["mol_id"][0]

    sql_query = f"""
    SELECT altitude, wave_no, optical_depth FROM optical_depths
    WHERE (wave_no BETWEEN {wave_no_min} and {wave_no_max}) and
    (altitude BETWEEN {alt_min} and {alt_max}) and
    (mol_id = {gas_id});
    """
    od_array = pd.read_sql_query(sql_query, connection).to_numpy()

    sql_alt_query = "SELECT DISTINCT altitude from optical_depths"
    alts = pd.read_sql_query(sql_alt_query, connection)
    alt_list = []
    for i in alts["altitude"]:
        if (i > alt_min) and (i < alt_max):
            alt_list.append(i)
    int_wave_no = np.rint(od_array[:, 1])
    od_dict = {}
    if verbose:
        for alt in tqdm(alt_list):
            mask = od_array[:, 0] == alt
            ods = od_array[:, 2][mask]
            wave_nos = int_wave_no[mask]
            binned_wave_nos, mean_ods = integer_bin_means(np.vstack((wave_nos, ods)))
            od_dict.update({int(alt): mean_ods})
    else:
        for alt in alt_list:
            mask = od_array[:, 0] == alt
            ods = od_array[:, 2][mask]
            wave_nos = int_wave_no[mask]
            binned_wave_nos, mean_ods = integer_bin_means(np.vstack((wave_nos, ods)))
            od_dict.update({int(alt): mean_ods})
    return od_dict, binned_wave_nos


def integer_bin_means(data: ArrayLike) -> Tuple[ArrayLike, ArrayLike]:
    # Have rounding in function, makes it more encapsulated.
    assert 2 in data.shape
    if data.shape[0] != 2:
        data = data.transpose()
    col_0_unique = np.unique(data[0])
    means = np.zeros_like(col_0_unique)
    for i, value in np.ndenumerate(col_0_unique):
        mask = data[0] == value
        means[i] = np.mean(data[1][mask])
    return col_0_unique, means


class AtmosphereGrid:
    def __init__(
        self,
        alt_range: Tuple[float, float],
        wave_no_range: Tuple[float, float],
        db_connection: sqlite3.Connection,
        *gas: str,
        verbose=False,
    ):
        self.alt_min, self.alt_max = alt_range
        self.wave_no_min, self.wave_no_max = wave_no_range
        self.connection = db_connection
        self.gases = gas
        self.verbose = verbose
        self.od_df, self.wave_no_bins = self.get_optical_depth()
        self.alt_list = self.od_df.columns.to_list()
        self.ones_grid = np.ones((len(self.alt_list), len(self.wave_no_bins)))

    def get_optical_depth(self):
        od_df = 0
        for _gas in self.gases:
            if self.verbose:
                tqdm.write(f"Loading {_gas} from Database")
            else:
                pass
            od_dict, wave_no_bins = fetch_od_from_db(
                self.connection,
                _gas,
                (self.alt_min, self.alt_max),
                (self.wave_no_min, self.wave_no_max),
                verbose=self.verbose
            )
            od_df += pd.DataFrame(od_dict)
        return od_df, wave_no_bins

    def get_blackbody_grid(self):
        temp_list = isa.get_temperature([int(i) for i in self.alt_list])
        temp_grid = (self.ones_grid.transpose() * temp_list).transpose()
        wave_no_grid = self.ones_grid * self.wave_no_bins.transpose()
        return plank_nu(wave_no_grid, temp_grid).transpose()

    def flux_up(self):
        ground_flux = plank_nu(self.wave_no_bins, isa.get_temperature(0))
        transmission_all_alt = np.exp(-self.od_df)
        blackbody_grid = self.get_blackbody_grid()
        # Initialise the transmission functions
        flux_from_surf = pd.DataFrame(
            (transmission_all_alt.transpose() * ground_flux).transpose()
        )
        flux_from_ith_block = (
            transmission_all_alt * blackbody_grid
        )  # wavenumber grid has spacing 1 cm^(-1) such that no multiplication is needed
        for i, _ in enumerate(flux_from_ith_block.iloc[0, :]):
            if i != 0:
                flux_from_ith_block.iloc[:, i] += flux_from_ith_block.iloc[:, i - 1]
                flux_from_surf.iloc[:, i - 1] *= flux_from_surf.iloc[:, i - 1]
        total_flux = flux_from_surf + flux_from_ith_block
        return pd.DataFrame(total_flux, columns=self.od_df.columns)


# %%
conn = sqlite3.connect(
    "/home/sean/Documents/Work/CDS_book/database_utitlites/optical_depth.db"
)
ag_test = AtmosphereGrid(
    (0, 10000),
    (200, 4000),
    conn,
    "H2O",
    "CO2",
    "CH4",
    "N2O",
    verbose=True
)


# %%

up_flux = ag_test.flux_up()
for i in up_flux:
    plt.plot(ag_test.wave_no_bins, up_flux[i])
plt.show()
