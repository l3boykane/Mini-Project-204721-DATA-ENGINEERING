'use client';
import React from 'react';
import { Card, Result } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';




export default function Home() {

	return (
		<div className="block-content-no-breadcrumb">
			<Card>
				<Result
					icon={<LineChartOutlined />}
					title="System Landslides in the northern region !"
				/>

				
			</Card>
		</div>
	);
}