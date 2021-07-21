# Trading alerts using Ichimoku Clouds indicator

## Disclaimers
 - Script is intented for alerting only and has no vocation to be used in order to decide what and when to LONG or SHORT actions on markets.
 - Alerts have then to be studied on a case by case basis in order to ensure risk / benefice ratio is worth trying.

## Licensing
 - &copy; Copyright Ludovic COURGNAUD 2020. All Rights Reserved.
 - Permission is granted for personal and Academic use only.
 - Code or portions of code may not be copied or used without appropriate credit given to author.

## Description
Automatic EMAIL alerts based on Ichimoku Clouds. For all markets, score (%) is then processed, based on the following conditions:
 -  Price position with Cloud [Under - Above]
 -  Price position with Kijun Sen [Under - Above]
 -  Price position with Chikou [Under - Above]
 -  Chikou position with Kijun Sen [Under - Above]
 -  Tenkan Sen position with Kijun Sen [Under - Above]
 -  Chikou position with SSB [Under - Above]

Score is then confirmed (or not) removing fake signals and contrary signals. Score is ignored if alert was already sent with equal or inferior score.

Note : Yahoo Finance Data is used in order to process Ichimoku Clouds.

## Usage
```python
usage: ./ichimoku.py [-h] [-f MARKETS_FILE] [-m MARKETS] [-i {30m,1h,4h,1d}]
                     [-c {9,26,52,7,22,44}] [-d] [-o {TXT,EMAIL,HTML}]
                     [-r REMOVE_VALUES] [-n] [-x] [-s SMTP_SERVER]
                     [-p SMTP_PORT] [-a SMTP_AUTH] [-t TO]

optional arguments:
  -h, --help            show this help message and exit
  -f MARKETS_FILE, --markets-file MARKETS_FILE
                        Input file containing markets to follow (one per
                        line).
  -m MARKETS, --markets MARKETS
                        Input string containing markets to follow (comma
                        separated).
  -i {30m,1h,4h,1d}, --interval {30m,1h,4h,1d}
                        Interval of stock data to process. Default '1h'.
  -c {9,26,52,7,22,44}, --config {9,26,52,7,22,44}
                        Ichimoku settings. Default '9,26,52'.
  -d, --debug           Activate debug mode. Default 'False'.
  -o {TXT,EMAIL,HTML}, --output {TXT,EMAIL,HTML}
                        Results output mode.
  -r REMOVE_VALUES, --remove-values REMOVE_VALUES
                        Number of values to be removed. Use for past analasys
                        only. Default 0.
  -n, --check-null      Perform second stock request if many null values.
                        Default 'False'.
  -x, --cloud-only      Process only scores for Cloud Signals (Up / Above).
                        Default 'False'.
  -s SMTP_SERVER, --smtp-server SMTP_SERVER
                        SMTP Server from which notification will be sent.
                        Default 'smtp.gmail.com'
  -p SMTP_PORT, --smtp-port SMTP_PORT
                        SMTP Server port from which notification will be sent.
                        Default '587'.
  -a SMTP_AUTH, --smtp-auth SMTP_AUTH
                        SMTP Server credentials (login:password).
  -t TO, --to TO        Email recipient(s) for notification ('a@a.com,
                        b@b.com').

Examples:
                python3 ichimoku.py -m MSFT -i 15m --txt
                python3 ichimoku.py -f ./markets.txt --html --debug
                python3 ichimoku.py -m 'MSFT, CS.PA' -r 'myemail@test.com' -a 'myemail@gmail.com:mypassword'
```

## Examples
### Example 1: Manual script execution on five markets, analysis on 1h interval, TXT output
```bash
# python3 ./ichimoku.py -m RPD,UNH,AMZN,AAPL,TEP.PA -i 1h -o TXT
SIGNALS 1h

LONG :
        - RPD : 100%

SHORT :
        - UNH : -83%
```
<p align="center" style="font-size: 1px;"><img align="center" src="/IMAGES/rpd.png?raw=true" height="300" /><br/><i>RPD BUY Signals</i></p>

### Example 2: Manual script execution on market file (>50 markets), analysis on 1d interval, TXT output
```bash
# python3 ichimoku.py -f eu_stocks.txt -i 1d -o TXT
SIGNALS 1d

LONG :
        - DHER_DE : 100%
        - BN_PA : 83%

SHORT :
        - ELIS_PA : -100%
        - RWE_DE : -100%
        - SPIE_PA : -100%
        - UBI_PA : -100%
        - ^FCHI : -83%
```
<p align="center" style="font-size: 1px;"><img align="center" src="/IMAGES/elis.png?raw=true" height="300" /><br/><i>ELIS.PA SHORT Signals</i></p>

### Example 3: Crontab execution on market file (>50 markets), analysis on 1d interval, EMAIL output
```bash
30 16 * * 1-5 python3 /[DIR]/ichimoku.py -f /[DIR]/eu_stocks.txt -i 1d -t '[RECIPIENT_EMAIL]' -a '[SENDER_EMAIL]:[SENDER_TOKEN]' -o EMAIL
```
<p align="center" style="font-size: 1px;"><img align="center" src="/IMAGES/email.png?raw=true" height="300" /><br/><i>Email Output</i></p>
