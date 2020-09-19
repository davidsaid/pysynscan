# Discovers stations in the local network

from synscan.motorizedbase import find_synscan_bases

if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.DEBUG)
    logging.info("Searching for bases")
    bases = find_synscan_bases()
    logging.info(f"Found {len(bases)}")
    logging.info(bases[0])
