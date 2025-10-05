'use client';
import React, { useEffect, useState, useRef, Fragment } from 'react';
import { Card, Skeleton } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import { DatePicker, Space, Breadcrumb, Row, Col, Typography, Spin } from 'antd';

import * as echarts from 'echarts';
import { API_BASE } from '@/lib/api';
import dayjs from 'dayjs';
import customParseFormat from 'dayjs/plugin/customParseFormat';
dayjs.extend(customParseFormat);
const dateFormat = 'YYYY-MM-DD';
type DateLimitOption = {
  minDate: any;
  maxDate: any;
};

type FilterOption = {
  date_filter: any;
};

type DataSourceRow = {
    date: any
    rain_mm_wmean: any
    province_id: number
    district_id: number
    province_name: string
    district_name: string
    province_name_en: string
    district_name_en: string
    risk_level: number
    count_of_disasters: number
};


type DataSource = [{
    date: any
    rain_mm_wmean: any
    province_id: number
    district_id: number
    province_name: string
    district_name: string
    province_name_en: string
    district_name_en: string
    risk_level: number
    count_of_disasters: number
}];

export default function Home() {
	const refChart = useRef<HTMLDivElement | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [dataSource, setDataSource] = useState<DataSource[]>([]);
	

	const [dateLimit, setDateLimit] = useState<DateLimitOption>({
		minDate : null,
		maxDate : null,
	});


	const [filterOption, setFilterOption] = useState<FilterOption>({
		date_filter : null,
	});

	const estimateProbability = (row: DataSourceRow): number => {
		// const rainFactor = row.rain_mm_wmean * 0.6;
		// const riskFactor = row.risk_level * 15;
		// const disasterFactor = row.count_of_disasters * 10;

		// const rainFactor = row.rain_mm_wmean / 2;
		// const riskFactor = row.risk_level * 10;
		// const disasterFactor = row.count_of_disasters * 5;
		// const total = rainFactor + riskFactor + disasterFactor;
		// return Math.min(100, total); // จำกัดไม่เกิน 100%

		const base = (row.rain_mm_wmean / 2) + (row.risk_level * 10);
		if (row.count_of_disasters > 0) {
			const boosted = base + row.count_of_disasters * 5;
			return Math.min(100, Math.max(80, boosted)); // อย่างน้อย 80%
		}
		return Math.min(100, base);
	}

	const handleChangeDate = (date: Dayjs | null, dateString: string) => {
		if(date) {
			setFilterOption({
				date_filter : dateString,
			})
		} else {
			setFilterOption({
				date_filter : dateLimit.maxDate,
			})
		}
	}

	useEffect(() => {
		async function fetchDataLimitDate(init: RequestInit = {}) {
			const resDay = await fetch(`${API_BASE}/get_date_limit`, { 
				cache: "no-store",
				credentials: 'include',
				headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
				...init,
			});

			const dataDate = await resDay.json()

			setDateLimit({
				maxDate: dataDate.max_date,
				minDate: dataDate.min_date
			})

			setFilterOption({
				date_filter : dataDate.max_date,
			})
		}

		fetchDataLimitDate();
	}, []);

	useEffect(() => {
		async function fetchDataGraph(date_filter=filterOption.date_filter, init: RequestInit = {}) {
			setIsLoading(true);

			try {

				const res = await fetch(`${API_BASE}/list_data_graph?date_filter=${date_filter}`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataGraph = await res.json()


				const obj = {};
				dataGraph.items.forEach((ele:any) => {
					obj[ele.district_name_en + '_' + ele.province_name_en] = ele;
				});

				const chart = echarts.init(refChart.current);

				await fetch('north_provinces_districts.geojson')
				.then((r) => r.json())
				.then((geojson) => {
					const dataChart = [];
					geojson.features.map((ele:any) => {
						const p = ele.properties || {};
						const province_en = (p.ADM1_EN ?? p.ADM1_EN ?? '').trim();
						const district_en = (p.ADM2_EN ?? p.ADM2_EN ?? '').trim();
						
						const dataGraph = obj[district_en + '_' + province_en];

						const dataEstimateProbability =  estimateProbability(dataGraph);
						// console.log('dataEstimateProbability', dataEstimateProbability);
						let colorArea = '#0a7f61';
						if(dataEstimateProbability >= 75) {
							colorArea = '#ad2029'
						} else if(dataEstimateProbability >= 50) {
							colorArea = '#c7982c'
						}
						p.DIST_KEY = 'อำเภอ : ' + dataGraph.district_name + ' จังหวัด : ' + dataGraph.province_name;
						dataChart.push({
							name: 'อำเภอ : ' + dataGraph.district_name + ' จังหวัด : ' + dataGraph.province_name, 
							value: dataGraph.dataEstimateProbability,
							rain_mm_wmean: dataGraph.rain_mm_wmean,
							province_name: dataGraph.province_name,
							province_name_en: dataGraph.province_name_en,
							district_name: dataGraph.district_name,
							district_name_en: dataGraph.district_name_en,
							risk_level : dataGraph.risk_level,
							count_of_disasters : dataGraph.count_of_disasters,
							itemStyle: {
								areaColor: colorArea,
								borderColor: '#9DA9B5',
								// borderColor: colorArea,
							},
							emphasis: {
								itemStyle: {
									areaColor: '#bdbaba'
								}
							},
							// label: {
							// 	show: true,
							// 	position: 'inside',
							// 	formatter: (p:any) => {
							// 		return `${p.data.dataEstimateProbability.toFixed(0) ?? 0}%`;
							// 	},
							// 	fontSize: 10,
							// 	color: '#ffffff'
							// }
						})
						
					});

					echarts.registerMap('TH_ADM2', geojson);
					
					chart.setOption({
						tooltip: {
							trigger: 'item',
							formatter: (p:any) => {
								return `
									<div>
									<b>จังหวัด: ${p.data.province_name} (${p.data.province_name_en})</b><br/>
									<b>อำเภอ : ${p.data.district_name} (${p.data.district_name_en})</b><br/>
									<b>ปริมาณฝน (mm): ${p.data.rain_mm_wmean ?? 0}</b><br />
									<b>ความเสี่ยงของพื้นที่: ${(p.data.risk_level == 1 ? 'ความเสี่ยงต่ำ (Low risk)' : (p.data.risk_level == 2 ? 'ความเสี่ยงปานกลาง (Medium risk)' : 'ความเสี่ยงสูง (High risk)'))}</b><br/>
									<b>จำนวนครั้งที่เกิดภัยพิบัติ: ${p.data.count_of_disasters ?? 0} ครั้ง</b><br />
									<b>ความเสี่ยง: ${p.value ?? 0}%</b><br />
									</div>
								`;
							}
						},
						visualMap: {
							show: true,
							type: 'piecewise',
							orient: 'vertical',
							top: 20,
							left: 20,
							itemWidth: 20,
							itemHeight: 14,
							textStyle: {
								fontSize: 13,
								color: '#333'
							},
							pieces: [
								{ value: 3, label: 'ความเสี่ยงสูง (High risk)', color: '#ad2029' },
								{ value: 2, label: 'ความเสี่ยงปานกลาง (Medium risk)', color: '#c7982c' },
								{ value: 1, label: 'ความเสี่ยงต่ำ (Low risk)', color: '#0a7f61' }
							],
							selectedMode: false,
							showLabel: true,
							hoverLink: false
						},
						series: [{
							type: 'map',
							top: 80,
							zoom: 1.2,
							map: 'TH_ADM2',
							nameProperty: 'DIST_KEY',
							roam: true,
							emphasis: { label: { show: false } },
							label: { show: false },
							data: dataChart,
						}]
					}, true);

					chart.resize();

					setTimeout(() => {
						setIsLoading(false);
						
					}, 1000);
				});
				

			} catch (e: any) {
				console.log('e', e);
				setDataSource([]);
			}
		}

		if(filterOption.date_filter != null) {
			fetchDataGraph();
		}
	}, [filterOption.date_filter]);

	return (
		<Fragment>
			<Breadcrumb className="breadcrumb-design" separator={`>`}
				items={[{ title: 'Home', href: '/', }]}
			/>
			<div className="block-content">
				<Row gutter={[16, 16]}>
					<Col span={24}>
						<Card className="pd-card-0" title={
							<Row>
								<Col span={16} className="position-relative">
									<Typography.Text className="iconHome">
										<LineChartOutlined />
									</Typography.Text>
									<Typography.Text className="textHome">
										Landslides in the northern region
									</Typography.Text>
								</Col>
								<Col span={8} className="text-right">
									{ 
										isLoading ?  <Skeleton.Input active/> : 
										<Space>
											<Typography.Text>วันที่ (Date) : </Typography.Text>
											<DatePicker
												onChange={handleChangeDate}
												defaultValue={dayjs(filterOption.date_filter, dateFormat)}
												minDate={dayjs(dateLimit.minDate, dateFormat)}
												maxDate={dayjs(dateLimit.maxDate, dateFormat)}
											/>
										</Space> 
									}
								</Col>
							</Row>
						}>
							<Spin spinning={isLoading} size={`large`}>
								<Row gutter={[24, 24]}>
									<Col span={24}>
										<div ref={refChart} style={{ width: '100%', height: '100vh' }} />
									</Col>
								</Row>
							</Spin>
						</Card>
					</Col>
				</Row>

			</div>
		</Fragment>
	);
}