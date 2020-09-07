<?php

namespace VPExchangeBot;

use TelegramBot\Api\Client;

class Bot extends Client
{
    public $wait_answer;
    public $start_wait_answer;
    public $wait_action;
    public $change_param_name = '';
    public $from_id;

    public $redis;

    public function __construct($token, $redis_host, $redis_db, $trackerToken = null)
    {
        parent::__construct($token, $trackerToken);
        $this->redis = new \Redis();
    	$this->redis->connect($redis_host);
    	$this->redis->select($redis_db);
    	$rawBody = json_decode($this->getRawBody(), true);
        $this->from_id = $rawBody['message']['from']['id'];
    	$this->wait_answer = $this->redis->get('tg:' . $this->from_id . ':wait_answer');
        $this->start_wait_answer = false;
        if ($this->wait_answer)
        {
            $this->change_param_name = $this->redis->get('tg:' . $this->from_id . ':change_param_name');
            $this->wait_action = $this->redis->get('tg:' . $this->from_id . ':wait_action');
        }
    }
}

?>