"""Facts about instruments and NeXus definitions, shared by ingest and the generator."""

from nxcat.models.metadata import Technique

# instrument name (upper case) -> (technique, facility)
INSTRUMENTS: dict[str, tuple[Technique, str]] = {
    "LET": (Technique.QENS, "ISIS"),
    "IRIS": (Technique.QENS, "ISIS"),
    "OSIRIS": (Technique.QENS, "ISIS"),
    "MARI": (Technique.INS, "ISIS"),
    "MAPS": (Technique.INS, "ISIS"),
    "SANS2D": (Technique.SANS, "ISIS"),
    "WISH": (Technique.DIFFRACTION, "ISIS"),
    "POLREF": (Technique.REFLECTOMETRY, "ISIS"),
    "BIFROST": (Technique.QENS, "ESS"),
    "LOKI": (Technique.SANS, "ESS"),
    "DREAM": (Technique.DIFFRACTION, "ESS"),
    "ESTIA": (Technique.REFLECTOMETRY, "ESS"),
    "ODIN": (Technique.IMAGING, "ESS"),
}

# NeXus application definition -> technique. Used only when the instrument is unknown.
# NXspe is missing on purpose: it is used for both QENS and INS, so it can't decide.
DEFINITION_TECHNIQUE: dict[str, Technique] = {
    "NXcanSAS": Technique.SANS,
    "NXsas": Technique.SANS,
    "NXmonopd": Technique.DIFFRACTION,
    "NXrefscan": Technique.REFLECTOMETRY,
    "NXtomo": Technique.IMAGING,
}

# Definition written by the generator for each technique.
TECHNIQUE_DEFINITION: dict[Technique, str] = {
    Technique.QENS: "NXspe",
    Technique.INS: "NXspe",
    Technique.SANS: "NXcanSAS",
    Technique.DIFFRACTION: "NXmonopd",
    Technique.REFLECTOMETRY: "NXrefscan",
    Technique.IMAGING: "NXtomo",
}
