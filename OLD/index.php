<!doctype html>

<html lang="en">
<head>
  <meta charset="utf-8">

  <title>Ichimoku Clouds (Ludovic COURGNAUD 2020)</title>
  <meta name="description" content="Trading Opportunities !">
  <meta name="author" content="Ludovic COURGNAUD">

</head>

<body>
<?php
	// Required field names
	$required = array('indice', 'time');

	// Loop over field names, make sure each one exists and is not empty
	$error = false;
	foreach($required as $field) {
		if (empty($_GET[$field])) {
		$error = true;
		}
	}

	if ($error) {
		echo "All fields are required.";
	} else {
		if ($_GET["btn"] == "close")
		{
			unlink('/home/ludo/Bureau/trading/MYTRADES/'. str_replace(".","_",$_GET['indice'])."_".$_GET['time']."_long");
			unlink('/home/ludo/Bureau/trading/MYTRADES/'. str_replace(".","_",$_GET['indice'])."_".$_GET['time']."_short");
		}
		else
		{
			touch('/home/ludo/Bureau/trading/MYTRADES/'. str_replace(".","_",$_GET['indice'])."_".$_GET['time']."_".$_GET['btn']);
		}
	}
	echo nl2br(shell_exec("ls /home/ludo/Bureau/trading/MYTRADES/"));
	echo "<br/>";
?>

<?php
	$filename1 = '/home/ludo/Bureau/trading/eu_stocks.txt';
	$filename2 = '/home/ludo/Bureau/trading/us_stocks.txt';
	$filename3 = '/home/ludo/Bureau/trading/mp_stocks.txt';

	$eachlines1 = file($filename1, FILE_IGNORE_NEW_LINES);
	$eachlines2 = file($filename2, FILE_IGNORE_NEW_LINES);
	$eachlines3 = file($filename3, FILE_IGNORE_NEW_LINES);

	$arr = [];
	$cpt = 0;
	foreach($eachlines1 as $lines){
		$arr[$cpt] = $lines;
		$cpt++;
	}
	foreach($eachlines2 as $lines){
		$arr[$cpt] = $lines;
		$cpt++;
	}
	foreach($eachlines3 as $lines){
		$arr[$cpt] = $lines;
		$cpt++;
	}

	sort($arr);
?>
<form action="./index.php" method="GET">
<div id="page-wrap">
        <select name="indice" id="indice">
            <option selected value="indice">Indice</option>
           <?php foreach($arr as $lines){ //add php code here
                echo "<option value='".$lines."'>$lines</option>";
            }?>
        </select>
        <select name="time" id="time">
            <option selected value="time">time</option>
            <option value='30m'>30 Minutes</option>";
            <option value='1h'>1 Hour</option>";
            <option value='4h'>4 Hours</option>";
            <option value='1d'>1 Day</option>";
        </select>
	<button name="btn" value="long">Long</button>
	<button name="btn" value="short">Short</button>
	<button name="btn" value="close">Close</button>
</div>
</form>
</body>
</html>
